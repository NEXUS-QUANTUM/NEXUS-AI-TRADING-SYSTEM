# ai/strategies/arbitrage/triangular_arbitrage.py
"""
NEXUS AI TRADING SYSTEM - Triangular Arbitrage Strategy
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class CurrencyPair:
    """Paire de devises"""
    base: str
    quote: str
    bid: float
    ask: float
    timestamp: datetime
    volume: float = 0.0

    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2

    def spread(self) -> float:
        return self.ask - self.bid

    def spread_percent(self) -> float:
        return (self.spread / self.mid_price()) * 100


@dataclass
class TriangularArbitrageOpportunity:
    """Opportunité d'arbitrage triangulaire"""
    path: List[str]  # ['USD', 'BTC', 'ETH', 'USD']
    pairs: List[str]  # ['USD/BTC', 'BTC/ETH', 'ETH/USD']
    rates: List[float]
    start_amount: float
    end_amount: float
    profit: float
    profit_percent: float
    confidence: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'pairs': self.pairs,
            'rates': self.rates,
            'start_amount': self.start_amount,
            'end_amount': self.end_amount,
            'profit': self.profit,
            'profit_percent': self.profit_percent,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class TriangularArbitrageConfig:
    """Configuration pour Triangular Arbitrage"""
    currencies: List[str] = field(default_factory=lambda: ['USD', 'BTC', 'ETH', 'SOL'])
    min_profit_percent: float = 0.1  # 0.1%
    max_position_size: float = 10000.0
    min_position_size: float = 100.0
    max_slippage: float = 0.001  # 0.1%
    fee_rate: float = 0.001  # 0.1%
    update_interval: float = 1.0  # secondes
    max_age: float = 5.0  # secondes
    min_confidence: float = 0.7
    max_paths: int = 10
    use_heuristic: bool = True
    execution_timeout: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'currencies': self.currencies,
            'min_profit_percent': self.min_profit_percent,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'max_slippage': self.max_slippage,
            'fee_rate': self.fee_rate,
            'update_interval': self.update_interval,
            'max_age': self.max_age,
            'min_confidence': self.min_confidence,
            'max_paths': self.max_paths,
            'use_heuristic': self.use_heuristic,
            'execution_timeout': self.execution_timeout,
        }


class TriangularArbitrage:
    """
    Stratégie d'arbitrage triangulaire.

    Features:
    - Triangular arbitrage detection
    - Real-time price monitoring
    - Path optimization
    - Risk management
    - Performance tracking

    Example:
        ```python
        config = TriangularArbitrageConfig(
            currencies=['USD', 'BTC', 'ETH'],
            min_profit_percent=0.1
        )
        strategy = TriangularArbitrage(config)

        # Update prices
        strategy.update_prices(prices)

        # Get opportunities
        opportunities = strategy.get_opportunities()
        ```
    """

    def __init__(self, config: Optional[TriangularArbitrageConfig] = None):
        self.config = config or TriangularArbitrageConfig()
        self.prices: Dict[str, Dict[str, CurrencyPair]] = {}
        self.opportunities: List[TriangularArbitrageOpportunity] = []
        self.executed_trades: List[Dict[str, Any]] = []

        # Initialisation des structures de prix
        for base in self.config.currencies:
            self.prices[base] = {}

        logger.info(f"TriangularArbitrage initialisé")

    def update_prices(self, prices: Dict[str, Dict[str, CurrencyPair]]) -> None:
        """
        Met à jour les prix.

        Args:
            prices: Dictionnaire des prix par paire
        """
        self.prices = prices
        self._detect_opportunities()

    def _detect_opportunities(self) -> None:
        """Détecte les opportunités d'arbitrage triangulaire"""
        self.opportunities = []

        # Génération des chemins
        paths = self._generate_paths()

        for path in paths:
            opportunity = self._evaluate_path(path)
            if opportunity and opportunity.profit_percent >= self.config.min_profit_percent:
                self.opportunities.append(opportunity)

        # Trier par profit
        self.opportunities.sort(key=lambda x: x.profit, reverse=True)

    def _generate_paths(self) -> List[List[str]]:
        """
        Génère les chemins pour l'arbitrage triangulaire.

        Returns:
            List[List[str]]: Chemins
        """
        if self.config.use_heuristic:
            return self._generate_heuristic_paths()
        else:
            return self._generate_all_paths()

    def _generate_all_paths(self) -> List[List[str]]:
        """Génère tous les chemins possibles"""
        paths = []
        n = len(self.config.currencies)

        for i in range(n):
            for j in range(n):
                for k in range(n):
                    if i != j and j != k and i != k:
                        path = [self.config.currencies[i], self.config.currencies[j], self.config.currencies[k], self.config.currencies[i]]
                        paths.append(path)

        return paths[:self.config.max_paths]

    def _generate_heuristic_paths(self) -> List[List[str]]:
        """
        Génère des chemins heuristiques.

        Returns:
            List[List[str]]: Chemins
        """
        # Chemins populaires
        common_paths = [
            ['USD', 'BTC', 'ETH', 'USD'],
            ['USD', 'BTC', 'SOL', 'USD'],
            ['USD', 'ETH', 'SOL', 'USD'],
            ['USD', 'BTC', 'ETH', 'SOL', 'USD'],
        ]

        # Chemins inverses
        reversed_paths = [[p[0], p[2], p[1], p[0]] for p in common_paths]

        all_paths = common_paths + reversed_paths
        return all_paths[:self.config.max_paths]

    def _evaluate_path(self, path: List[str]) -> Optional[TriangularArbitrageOpportunity]:
        """
        Évalue un chemin d'arbitrage.

        Args:
            path: Chemin à évaluer

        Returns:
            Optional[TriangularArbitrageOpportunity]: Opportunité
        """
        # Récupération des prix
        pairs = []
        rates = []

        for i in range(len(path) - 1):
            base = path[i]
            quote = path[i + 1]

            if base in self.prices and quote in self.prices[base]:
                pair = self.prices[base][quote]
                pairs.append(f"{base}/{quote}")
                rates.append(pair.bid if i % 2 == 0 else pair.ask)
            else:
                # Essayer l'ordre inverse
                if quote in self.prices and base in self.prices[quote]:
                    pair = self.prices[quote][base]
                    pairs.append(f"{base}/{quote}")
                    # Inverser le taux
                    rate = 1 / pair.ask if i % 2 == 0 else 1 / pair.bid
                    rates.append(rate)
                else:
                    return None

        # Calcul du profit
        start_amount = self.config.min_position_size
        current_amount = start_amount

        # Vérification de la fraîcheur des données
        for pair in pairs:
            # Vérification simplifiée
            pass

        # Calcul du profit
        for rate in rates:
            current_amount *= rate

        # Frais
        fees = current_amount * self.config.fee_rate
        end_amount = current_amount - fees
        profit = end_amount - start_amount
        profit_percent = (profit / start_amount) * 100

        # Confiance
        confidence = self._calculate_confidence(path)

        if profit > 0:
            return TriangularArbitrageOpportunity(
                path=path,
                pairs=pairs,
                rates=rates,
                start_amount=start_amount,
                end_amount=end_amount,
                profit=profit,
                profit_percent=profit_percent,
                confidence=confidence,
                timestamp=datetime.now(),
            )

        return None

    def _calculate_confidence(self, path: List[str]) -> float:
        """
        Calcule la confiance pour un chemin.

        Args:
            path: Chemin

        Returns:
            float: Niveau de confiance
        """
        factors = []

        # 1. Fraîcheur des données
        freshness = 1.0
        for i in range(len(path) - 1):
            base = path[i]
            quote = path[i + 1]
            if base in self.prices and quote in self.prices[base]:
                pair = self.prices[base][quote]
                age = (datetime.now() - pair.timestamp).seconds
                freshness *= max(0, 1 - age / self.config.max_age)

        factors.append(freshness)

        # 2. Liquidité
        liquidity = 1.0
        for i in range(len(path) - 1):
            base = path[i]
            quote = path[i + 1]
            if base in self.prices and quote in self.prices[base]:
                pair = self.prices[base][quote]
                liquidity *= min(1, pair.volume / 1000)

        factors.append(liquidity)

        # 3. Spread
        spread_factor = 1.0
        for i in range(len(path) - 1):
            base = path[i]
            quote = path[i + 1]
            if base in self.prices and quote in self.prices[base]:
                pair = self.prices[base][quote]
                spread_factor *= (1 - pair.spread_percent() / 100)

        factors.append(spread_factor)

        return np.mean(factors)

    def get_opportunities(self) -> List[TriangularArbitrageOpportunity]:
        """
        Retourne les opportunités d'arbitrage.

        Returns:
            List[TriangularArbitrageOpportunity]: Opportunités
        """
        return self.opportunities

    def get_best_opportunity(self) -> Optional[TriangularArbitrageOpportunity]:
        """
        Retourne la meilleure opportunité.

        Returns:
            Optional[TriangularArbitrageOpportunity]: Meilleure opportunité
        """
        opportunities = self.get_opportunities()
        if not opportunities:
            return None

        # Filtrer par confiance
        valid = [o for o in opportunities if o.confidence >= self.config.min_confidence]
        if not valid:
            return None

        return max(valid, key=lambda x: x.profit)

    def execute(self, opportunity: TriangularArbitrageOpportunity) -> Dict[str, Any]:
        """
        Exécute une opportunité d'arbitrage.

        Args:
            opportunity: Opportunité à exécuter

        Returns:
            Dict[str, Any]: Résultat de l'exécution
        """
        if opportunity.confidence < self.config.min_confidence:
            return {'status': 'rejected', 'reason': 'low_confidence'}

        # Simulation d'exécution
        import time
        time.sleep(0.5)

        # Vérification des prix
        execution_rates = []

        for path in opportunity.path:
            # Simulation de slippage
            slippage = np.random.uniform(0, self.config.max_slippage)
            rate = opportunity.rates[0] * (1 + np.random.normal(0, slippage))
            execution_rates.append(rate)

        # Calcul du profit réel
        start_amount = opportunity.start_amount
        current_amount = start_amount

        for rate in execution_rates:
            current_amount *= rate

        fees = current_amount * self.config.fee_rate
        end_amount = current_amount - fees
        net_profit = end_amount - start_amount

        trade = {
            'status': 'executed' if net_profit > 0 else 'partial',
            'path': opportunity.path,
            'pairs': opportunity.pairs,
            'start_amount': start_amount,
            'end_amount': end_amount,
            'expected_profit': opportunity.profit,
            'actual_profit': net_profit,
            'slippage': np.mean(np.abs(np.array(execution_rates) - np.array(opportunity.rates))),
            'timestamp': datetime.now(),
            'opportunity': opportunity.to_dict(),
        }

        self.executed_trades.append(trade)

        logger.info(f"Trade exécuté: {opportunity.path} - Profit: ${net_profit:.2f}")

        return trade

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de la stratégie.

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

        profits = [t['actual_profit'] for t in self.executed_trades]
        wins = [p for p in profits if p > 0]

        return {
            'total_trades': len(self.executed_trades),
            'total_profit': sum(profits),
            'win_rate': len(wins) / len(profits) if profits else 0.0,
            'avg_profit': np.mean(profits) if profits else 0.0,
            'max_profit': max(profits) if profits else 0.0,
            'min_profit': min(profits) if profits else 0.0,
            'total_volume': sum(t['start_amount'] for t in self.executed_trades),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la stratégie.

        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'currencies': self.config.currencies,
            'opportunities_count': len(self.opportunities),
            'trades_count': len(self.executed_trades),
            'best_opportunity': self.get_best_opportunity().to_dict() if self.get_best_opportunity() else None,
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde la stratégie.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardée
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

            logger.info(f"Stratégie sauvegardée: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'TriangularArbitrage':
        """
        Charge une stratégie.

        Args:
            filepath: Chemin du fichier

        Returns:
            TriangularArbitrage: Stratégie chargée
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = TriangularArbitrageConfig(**data['config'])
            strategy = cls(config)

            strategy.executed_trades = data.get('executed_trades', [])

            logger.info(f"Stratégie chargée: {filepath}")
            return strategy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_triangular_arbitrage(
    currencies: List[str] = None,
    min_profit_percent: float = 0.1,
    **kwargs
) -> TriangularArbitrage:
    """
    Factory pour créer une stratégie d'arbitrage triangulaire.

    Args:
        currencies: Liste des devises
        min_profit_percent: Profit minimum en pourcentage
        **kwargs: Arguments supplémentaires

    Returns:
        TriangularArbitrage: Stratégie d'arbitrage triangulaire
    """
    if currencies is None:
        currencies = ['USD', 'BTC', 'ETH', 'SOL']

    config = TriangularArbitrageConfig(
        currencies=currencies,
        min_profit_percent=min_profit_percent,
        **kwargs
    )
    return TriangularArbitrage(config)


__all__ = [
    'TriangularArbitrage',
    'TriangularArbitrageConfig',
    'CurrencyPair',
    'TriangularArbitrageOpportunity',
    'create_triangular_arbitrage',
]

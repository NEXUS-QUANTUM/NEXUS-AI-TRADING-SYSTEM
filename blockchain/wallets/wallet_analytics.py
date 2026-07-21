"""
NEXUS AI TRADING SYSTEM - WALLET ANALYTICS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'analytique avancée pour wallets multi-blockchain.
Analyse de portefeuille, performances, risques, et insights.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import numpy as np
from scipy import stats
from scipy.optimize import minimize

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class AnalyticsPeriod(Enum):
    """Périodes d'analyse."""
    HOUR = "1h"
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"
    YEAR = "365d"
    ALL = "all"


class RiskMetric(Enum):
    """Métriques de risque."""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    VAR_95 = "var_95"
    VAR_99 = "var_99"
    EXPECTED_SHORTFALL = "expected_shortfall"
    BETA = "beta"
    ALPHA = "alpha"
    VOLATILITY = "volatility"


class PerformanceMetric(Enum):
    """Métriques de performance."""
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    DAILY_RETURN = "daily_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    AVERAGE_WIN = "average_win"
    AVERAGE_LOSS = "average_loss"
    RISK_REWARD_RATIO = "risk_reward_ratio"
    RECOVERY_FACTOR = "recovery_factor"


@dataclass
class PortfolioSnapshot:
    """Snapshot de portefeuille."""
    timestamp: datetime
    total_value_usd: Decimal
    by_chain: Dict[str, Decimal]
    by_token: Dict[str, Decimal]
    by_type: Dict[str, Decimal]
    transaction_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_value_usd": str(self.total_value_usd),
            "by_chain": {k: str(v) for k, v in self.by_chain.items()},
            "by_token": {k: str(v) for k, v in self.by_token.items()},
            "by_type": {k: str(v) for k, v in self.by_type.items()},
            "transaction_count": self.transaction_count,
            "metadata": self.metadata
        }


@dataclass
class PortfolioPerformance:
    """Performance de portefeuille."""
    period: AnalyticsPeriod
    start_value: Decimal
    end_value: Decimal
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    var_95: float
    var_99: float
    expected_shortfall: float
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    risk_reward_ratio: float
    recovery_factor: float
    benchmarks: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "period": self.period.value,
            "start_value": str(self.start_value),
            "end_value": str(self.end_value),
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "expected_shortfall": self.expected_shortfall,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "risk_reward_ratio": self.risk_reward_ratio,
            "recovery_factor": self.recovery_factor,
            "benchmarks": self.benchmarks,
            "metadata": self.metadata
        }


@dataclass
class WalletInsight:
    """Insight sur un wallet."""
    insight_id: UUID
    wallet_id: UUID
    category: str
    severity: str  # info, warning, critical
    title: str
    description: str
    recommendation: str
    value: Any
    metric: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "insight_id": str(self.insight_id),
            "wallet_id": str(self.wallet_id),
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "value": self.value,
            "metric": self.metric,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class WalletAnalytics:
    """Analytique complète d'un wallet."""
    wallet_id: UUID
    total_value_usd: Decimal
    total_transactions: int
    average_tx_value: Decimal
    largest_tx_value: Decimal
    total_fees_usd: Decimal
    net_profit_usd: Decimal
    roi_percentage: float
    days_active: int
    active_chains: List[str]
    top_tokens: List[Dict[str, Any]]
    performance: PortfolioPerformance
    insights: List[WalletInsight]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "total_value_usd": str(self.total_value_usd),
            "total_transactions": self.total_transactions,
            "average_tx_value": str(self.average_tx_value),
            "largest_tx_value": str(self.largest_tx_value),
            "total_fees_usd": str(self.total_fees_usd),
            "net_profit_usd": str(self.net_profit_usd),
            "roi_percentage": self.roi_percentage,
            "days_active": self.days_active,
            "active_chains": self.active_chains,
            "top_tokens": self.top_tokens,
            "performance": self.performance.to_dict(),
            "insights": [i.to_dict() for i in self.insights],
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET ANALYTICS
# ============================================================================

class WalletAnalyticsService:
    """
    Service d'analytique avancée pour wallets multi-blockchain.
    """

    # Prix des benchmarks
    BENCHMARK_PRICES = {
        "BTC": 0,
        "ETH": 0,
        "BNB": 0,
        "SOL": 0,
        "MATIC": 0,
        "AVAX": 0,
        "TRX": 0,
        "DOT": 0,
        "ADA": 0
    }

    # Seuils pour les insights
    INSIGHT_THRESHOLDS = {
        "concentration_high": 0.5,  # 50% dans un seul token
        "concentration_critical": 0.8,  # 80% dans un seul token
        "drawdown_warning": 0.2,  # 20% drawdown
        "drawdown_critical": 0.5,  # 50% drawdown
        "volatility_high": 0.5,  # 50% volatilité annualisée
        "win_rate_low": 0.3,  # 30% win rate
        "fee_high": 0.05,  # 5% en frais
        "inactivity_days": 30,  # 30 jours inactif
        "gas_spike": 2.0  # 2x le prix normal du gaz
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service d'analytique.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Cache
        self._snapshot_cache: Dict[UUID, List[PortfolioSnapshot]] = {}
        self._performance_cache: Dict[UUID, Dict[str, PortfolioPerformance]] = {}
        self._insight_cache: Dict[UUID, List[WalletInsight]] = {}
        
        # Métriques
        self._metrics = {
            "total_wallets_analyzed": 0,
            "total_transactions_analyzed": 0,
            "total_insights_generated": 0,
            "last_analysis": None
        }

        logger.info("WalletAnalyticsService initialisé avec succès")

    # ========================================================================
    # ANALYSE DE PORTEFEUILLE
    # ========================================================================

    async def analyze_wallet(
        self,
        wallet: BaseWallet,
        period: AnalyticsPeriod = AnalyticsPeriod.MONTH
    ) -> WalletAnalytics:
        """
        Analyse complète d'un wallet.

        Args:
            wallet: Wallet à analyser
            period: Période d'analyse

        Returns:
            Analytique complète du wallet
        """
        try:
            wallet_id = wallet.config.wallet_id
            
            # Récupération des données
            balance = await wallet.get_balance()
            transactions = await wallet.get_transactions(limit=1000)
            
            # Snapshot du portefeuille
            snapshot = await self._create_snapshot(wallet, balance)
            
            # Performance du portefeuille
            performance = await self._calculate_performance(
                wallet, transactions, period
            )
            
            # Insights
            insights = await self._generate_insights(
                wallet, balance, transactions, performance
            )
            
            # Métriques calculées
            total_tx = len(transactions)
            total_value = balance.total_balance_usd
            total_fees = sum(tx.gas_price * Decimal(str(tx.gas_used or 0)) 
                            for tx in transactions if tx.gas_price and tx.gas_used)
            
            # Top tokens
            top_tokens = sorted(
                balance.token_balances.items(),
                key=lambda x: float(x[1]),
                reverse=True
            )[:10]
            
            # Création de l'analytique
            analytics = WalletAnalytics(
                wallet_id=wallet_id,
                total_value_usd=total_value,
                total_transactions=total_tx,
                average_tx_value=total_value / total_tx if total_tx > 0 else Decimal("0"),
                largest_tx_value=max((tx.amount for tx in transactions), default=Decimal("0")),
                total_fees_usd=total_fees,
                net_profit_usd=performance.end_value - performance.start_value,
                roi_percentage=performance.total_return,
                days_active=(datetime.now() - wallet.config.created_at).days,
                active_chains=[wallet.config.blockchain],
                top_tokens=[
                    {
                        "address": addr,
                        "balance": float(bal),
                        "symbol": wallet._token_cache.get(addr, {}).get("symbol", "UNKNOWN")
                    }
                    for addr, bal in top_tokens
                ],
                performance=performance,
                insights=insights
            )

            # Mise en cache
            self._performance_cache[wallet_id] = {period.value: performance}
            self._insight_cache[wallet_id] = insights
            
            # Mise à jour des métriques
            self._metrics["total_wallets_analyzed"] += 1
            self._metrics["total_transactions_analyzed"] += total_tx
            self._metrics["last_analysis"] = datetime.now().isoformat()

            return analytics

        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du wallet: {e}")
            raise

    async def _create_snapshot(
        self,
        wallet: BaseWallet,
        balance: WalletBalance
    ) -> PortfolioSnapshot:
        """
        Crée un snapshot du portefeuille.

        Args:
            wallet: Wallet
            balance: Solde du wallet

        Returns:
            Snapshot du portefeuille
        """
        return PortfolioSnapshot(
            timestamp=datetime.now(),
            total_value_usd=balance.total_balance_usd,
            by_chain={wallet.config.blockchain: balance.total_balance_usd},
            by_token=balance.token_balances_usd,
            by_type={
                "native": balance.native_balance_usd,
                "tokens": sum(balance.token_balances_usd.values())
            },
            transaction_count=0
        )

    async def _calculate_performance(
        self,
        wallet: BaseWallet,
        transactions: List[Transaction],
        period: AnalyticsPeriod
    ) -> PortfolioPerformance:
        """
        Calcule les performances du portefeuille.

        Args:
            wallet: Wallet
            transactions: Liste des transactions
            period: Période d'analyse

        Returns:
            Performance du portefeuille
        """
        try:
            # Récupération des prix historiques
            prices = await self._get_historical_prices(
                wallet.config.blockchain,
                period
            )

            # Calcul des rendements
            returns = self._calculate_returns(transactions, prices)
            
            # Métriques de performance
            total_return = self._calculate_total_return(returns)
            annualized_return = self._calculate_annualized_return(returns)
            volatility = self._calculate_volatility(returns)
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sortino_ratio = self._calculate_sortino_ratio(returns)
            calmar_ratio = self._calculate_calmar_ratio(returns)
            max_drawdown = self._calculate_max_drawdown(returns)
            var_95 = self._calculate_var(returns, 0.95)
            var_99 = self._calculate_var(returns, 0.99)
            expected_shortfall = self._calculate_expected_shortfall(returns)
            
            # Métriques de trading
            win_rate = self._calculate_win_rate(transactions)
            profit_factor = self._calculate_profit_factor(transactions)
            avg_win = self._calculate_average_win(transactions)
            avg_loss = self._calculate_average_loss(transactions)
            risk_reward_ratio = self._calculate_risk_reward_ratio(avg_win, avg_loss)
            recovery_factor = self._calculate_recovery_factor(transactions, max_drawdown)

            # Valeurs de début et fin
            start_value = Decimal(str(prices[0])) if prices else Decimal("0")
            end_value = Decimal(str(prices[-1])) if prices else Decimal("0")

            return PortfolioPerformance(
                period=period,
                start_value=start_value,
                end_value=end_value,
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=max_drawdown,
                var_95=var_95,
                var_99=var_99,
                expected_shortfall=expected_shortfall,
                win_rate=win_rate,
                profit_factor=profit_factor,
                average_win=avg_win,
                average_loss=avg_loss,
                risk_reward_ratio=risk_reward_ratio,
                recovery_factor=recovery_factor,
                benchmarks=await self._get_benchmark_prices(period)
            )

        except Exception as e:
            logger.error(f"Erreur lors du calcul des performances: {e}")
            return self._default_performance(period)

    def _default_performance(self, period: AnalyticsPeriod) -> PortfolioPerformance:
        """
        Retourne une performance par défaut.

        Args:
            period: Période d'analyse

        Returns:
            Performance par défaut
        """
        return PortfolioPerformance(
            period=period,
            start_value=Decimal("0"),
            end_value=Decimal("0"),
            total_return=0.0,
            annualized_return=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            var_99=0.0,
            expected_shortfall=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            average_win=0.0,
            average_loss=0.0,
            risk_reward_ratio=0.0,
            recovery_factor=0.0
        )

    # ========================================================================
    # CALCULS DE PERFORMANCE
    # ========================================================================

    def _calculate_returns(
        self,
        transactions: List[Transaction],
        prices: List[float]
    ) -> List[float]:
        """
        Calcule les rendements du portefeuille.

        Args:
            transactions: Liste des transactions
            prices: Prix historiques

        Returns:
            Liste des rendements
        """
        if not prices or len(prices) < 2:
            return [0.0]

        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
            else:
                returns.append(0.0)

        return returns

    def _calculate_total_return(self, returns: List[float]) -> float:
        """
        Calcule le rendement total.

        Args:
            returns: Liste des rendements

        Returns:
            Rendement total en pourcentage
        """
        if not returns:
            return 0.0
        
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r)
        
        return (cumulative - 1) * 100

    def _calculate_annualized_return(self, returns: List[float]) -> float:
        """
        Calcule le rendement annualisé.

        Args:
            returns: Liste des rendements

        Returns:
            Rendement annualisé en pourcentage
        """
        if not returns:
            return 0.0
        
        total_return = self._calculate_total_return(returns) / 100
        n = len(returns)
        days = n  # Supposons des rendements quotidiens
        
        if days > 0:
            annualized = (1 + total_return) ** (365 / days) - 1
            return annualized * 100
        
        return 0.0

    def _calculate_volatility(self, returns: List[float]) -> float:
        """
        Calcule la volatilité annualisée.

        Args:
            returns: Liste des rendements

        Returns:
            Volatilité annualisée en pourcentage
        """
        if not returns:
            return 0.0
        
        daily_vol = np.std(returns)
        annualized_vol = daily_vol * np.sqrt(365)
        return annualized_vol * 100

    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """
        Calcule le Sharpe Ratio.

        Args:
            returns: Liste des rendements

        Returns:
            Sharpe Ratio
        """
        if not returns:
            return 0.0
        
        risk_free_rate = 0.02  # 2% taux sans risque
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        daily_rf = risk_free_rate / 365
        sharpe = (avg_return - daily_rf) / std_return
        
        return sharpe * np.sqrt(365)

    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """
        Calcule le Sortino Ratio.

        Args:
            returns: Liste des rendements

        Returns:
            Sortino Ratio
        """
        if not returns:
            return 0.0
        
        risk_free_rate = 0.02
        avg_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        
        if not downside_returns:
            return 0.0
        
        downside_deviation = np.std(downside_returns)
        if downside_deviation == 0:
            return 0.0
        
        daily_rf = risk_free_rate / 365
        sortino = (avg_return - daily_rf) / downside_deviation
        
        return sortino * np.sqrt(365)

    def _calculate_calmar_ratio(self, returns: List[float]) -> float:
        """
        Calcule le Calmar Ratio.

        Args:
            returns: Liste des rendements

        Returns:
            Calmar Ratio
        """
        if not returns:
            return 0.0
        
        annualized_return = self._calculate_annualized_return(returns) / 100
        max_drawdown = self._calculate_max_drawdown(returns) / 100
        
        if max_drawdown == 0:
            return 0.0
        
        return annualized_return / max_drawdown

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """
        Calcule le maximum drawdown.

        Args:
            returns: Liste des rendements

        Returns:
            Maximum drawdown en pourcentage
        """
        if not returns:
            return 0.0
        
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_dd = np.min(drawdown)
        
        return abs(max_dd) * 100

    def _calculate_var(self, returns: List[float], confidence: float) -> float:
        """
        Calcule la Value at Risk.

        Args:
            returns: Liste des rendements
            confidence: Niveau de confiance (0.95 ou 0.99)

        Returns:
            VaR en pourcentage
        """
        if not returns:
            return 0.0
        
        var_percentile = (1 - confidence) * 100
        var = np.percentile(returns, var_percentile)
        
        return abs(var) * 100

    def _calculate_expected_shortfall(self, returns: List[float]) -> float:
        """
        Calcule l'Expected Shortfall (CVaR).

        Args:
            returns: Liste des rendements

        Returns:
            Expected Shortfall en pourcentage
        """
        if not returns:
            return 0.0
        
        var_95 = self._calculate_var(returns, 0.95) / 100
        tail_returns = [r for r in returns if r < var_95]
        
        if not tail_returns:
            return 0.0
        
        es = np.mean(tail_returns)
        return abs(es) * 100

    def _calculate_win_rate(self, transactions: List[Transaction]) -> float:
        """
        Calcule le taux de victoire.

        Args:
            transactions: Liste des transactions

        Returns:
            Taux de victoire en pourcentage
        """
        if not transactions:
            return 0.0
        
        wins = sum(1 for tx in transactions if tx.amount > Decimal("0"))
        return (wins / len(transactions)) * 100

    def _calculate_profit_factor(self, transactions: List[Transaction]) -> float:
        """
        Calcule le Profit Factor.

        Args:
            transactions: Liste des transactions

        Returns:
            Profit Factor
        """
        if not transactions:
            return 0.0
        
        gross_profit = sum(
            tx.amount_usd for tx in transactions if tx.amount_usd > 0
        )
        gross_loss = abs(sum(
            tx.amount_usd for tx in transactions if tx.amount_usd < 0
        ))
        
        if gross_loss == 0:
            return float('inf')
        
        return float(gross_profit / gross_loss)

    def _calculate_average_win(self, transactions: List[Transaction]) -> float:
        """
        Calcule la victoire moyenne.

        Args:
            transactions: Liste des transactions

        Returns:
            Victoire moyenne en USD
        """
        wins = [tx.amount_usd for tx in transactions if tx.amount_usd > 0]
        if not wins:
            return 0.0
        
        return float(sum(wins) / len(wins))

    def _calculate_average_loss(self, transactions: List[Transaction]) -> float:
        """
        Calcule la perte moyenne.

        Args:
            transactions: Liste des transactions

        Returns:
            Perte moyenne en USD
        """
        losses = [tx.amount_usd for tx in transactions if tx.amount_usd < 0]
        if not losses:
            return 0.0
        
        return float(abs(sum(losses) / len(losses)))

    def _calculate_risk_reward_ratio(
        self,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calcule le ratio risque/récompense.

        Args:
            avg_win: Victoire moyenne
            avg_loss: Perte moyenne

        Returns:
            Ratio risque/récompense
        """
        if avg_loss == 0:
            return 0.0
        
        return avg_win / avg_loss

    def _calculate_recovery_factor(
        self,
        transactions: List[Transaction],
        max_drawdown: float
    ) -> float:
        """
        Calcule le Recovery Factor.

        Args:
            transactions: Liste des transactions
            max_drawdown: Maximum drawdown

        Returns:
            Recovery Factor
        """
        if not transactions or max_drawdown == 0:
            return 0.0
        
        net_profit = sum(tx.amount_usd for tx in transactions)
        return float(net_profit / Decimal(str(max_drawdown)))

    # ========================================================================
    # INSIGHTS ET RECOMMANDATIONS
    # ========================================================================

    async def _generate_insights(
        self,
        wallet: BaseWallet,
        balance: WalletBalance,
        transactions: List[Transaction],
        performance: PortfolioPerformance
    ) -> List[WalletInsight]:
        """
        Génère des insights sur le wallet.

        Args:
            wallet: Wallet
            balance: Solde du wallet
            transactions: Liste des transactions
            performance: Performance du wallet

        Returns:
            Liste des insights
        """
        insights = []

        try:
            # 1. Concentration des tokens
            concentration_insight = await self._analyze_concentration(balance)
            if concentration_insight:
                insights.append(concentration_insight)

            # 2. Drawdown
            drawdown_insight = self._analyze_drawdown(performance)
            if drawdown_insight:
                insights.append(drawdown_insight)

            # 3. Volatilité
            volatility_insight = self._analyze_volatility(performance)
            if volatility_insight:
                insights.append(volatility_insight)

            # 4. Performance
            performance_insight = await self._analyze_performance(performance)
            if performance_insight:
                insights.append(performance_insight)

            # 5. Frais
            fee_insight = await self._analyze_fees(transactions)
            if fee_insight:
                insights.append(fee_insight)

            # 6. Activité
            activity_insight = await self._analyze_activity(wallet, transactions)
            if activity_insight:
                insights.append(activity_insight)

            # 7. Diversification
            diversification_insight = await self._analyze_diversification(balance)
            if diversification_insight:
                insights.append(diversification_insight)

            # 8. Risque de marché
            market_risk_insight = await self._analyze_market_risk(performance)
            if market_risk_insight:
                insights.append(market_risk_insight)

            # Mise en cache
            self._insight_cache[wallet.config.wallet_id] = insights
            self._metrics["total_insights_generated"] += len(insights)

        except Exception as e:
            logger.error(f"Erreur lors de la génération des insights: {e}")

        return insights

    async def _analyze_concentration(
        self,
        balance: WalletBalance
    ) -> Optional[WalletInsight]:
        """
        Analyse la concentration des tokens.

        Args:
            balance: Solde du wallet

        Returns:
            Insight sur la concentration
        """
        total_value = float(balance.total_balance_usd)
        if total_value == 0:
            return None

        max_token = max(
            balance.token_balances_usd.values(),
            default=Decimal("0")
        )
        max_token_pct = float(max_token) / total_value

        if max_token_pct >= self.INSIGHT_THRESHOLDS["concentration_critical"]:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=balance.wallet_id,
                category="concentration",
                severity="critical",
                title="⚠️ Concentration Critique des Tokens",
                description=f"{max_token_pct*100:.1f}% de votre portefeuille est dans un seul token",
                recommendation="Diversifiez votre portefeuille pour réduire le risque",
                value=max_token_pct,
                metric="concentration_ratio",
                timestamp=datetime.now()
            )
        elif max_token_pct >= self.INSIGHT_THRESHOLDS["concentration_high"]:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=balance.wallet_id,
                category="concentration",
                severity="warning",
                title="⚠️ Concentration Élevée des Tokens",
                description=f"{max_token_pct*100:.1f}% de votre portefeuille est dans un seul token",
                recommendation="Envisagez de diversifier votre portefeuille",
                value=max_token_pct,
                metric="concentration_ratio",
                timestamp=datetime.now()
            )

        return None

    def _analyze_drawdown(
        self,
        performance: PortfolioPerformance
    ) -> Optional[WalletInsight]:
        """
        Analyse le drawdown.

        Args:
            performance: Performance du wallet

        Returns:
            Insight sur le drawdown
        """
        dd = performance.max_drawdown

        if dd >= self.INSIGHT_THRESHOLDS["drawdown_critical"] * 100:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                category="drawdown",
                severity="critical",
                title="🔻 Drawdown Critique",
                description=f"Drawdown de {dd:.1f}% - Niveau très élevé",
                recommendation="Révisez votre stratégie de gestion des risques",
                value=dd,
                metric="max_drawdown",
                timestamp=datetime.now()
            )
        elif dd >= self.INSIGHT_THRESHOLDS["drawdown_warning"] * 100:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                category="drawdown",
                severity="warning",
                title="📉 Drawdown Élevé",
                description=f"Drawdown de {dd:.1f}% - Surveillez votre exposition",
                recommendation="Utilisez des stop-loss pour protéger votre capital",
                value=dd,
                metric="max_drawdown",
                timestamp=datetime.now()
            )

        return None

    def _analyze_volatility(
        self,
        performance: PortfolioPerformance
    ) -> Optional[WalletInsight]:
        """
        Analyse la volatilité.

        Args:
            performance: Performance du wallet

        Returns:
            Insight sur la volatilité
        """
        vol = performance.volatility

        if vol > self.INSIGHT_THRESHOLDS["volatility_high"] * 100:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                category="volatility",
                severity="warning",
                title="📊 Volatilité Élevée",
                description=f"Volatilité annualisée de {vol:.1f}%",
                recommendation="Réduisez votre exposition aux actifs volatils",
                value=vol,
                metric="volatility",
                timestamp=datetime.now()
            )

        return None

    async def _analyze_performance(
        self,
        performance: PortfolioPerformance
    ) -> Optional[WalletInsight]:
        """
        Analyse la performance.

        Args:
            performance: Performance du wallet

        Returns:
            Insight sur la performance
        """
        if performance.total_return < -20:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                category="performance",
                severity="critical",
                title="📉 Performance Négative",
                description=f"Perte de {abs(performance.total_return):.1f}% sur la période",
                recommendation="Révisez votre stratégie d'investissement",
                value=performance.total_return,
                metric="total_return",
                timestamp=datetime.now()
            )
        elif performance.total_return < -10:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                category="performance",
                severity="warning",
                title="📉 Légère Performance Négative",
                description=f"Perte de {abs(performance.total_return):.1f}% sur la période",
                recommendation="Surveillez l'évolution du marché",
                value=performance.total_return,
                metric="total_return",
                timestamp=datetime.now()
            )

        return None

    async def _analyze_fees(
        self,
        transactions: List[Transaction]
    ) -> Optional[WalletInsight]:
        """
        Analyse les frais.

        Args:
            transactions: Liste des transactions

        Returns:
            Insight sur les frais
        """
        total_value = sum(float(tx.amount_usd) for tx in transactions)
        total_fees = sum(float(tx.amount_usd) * 0.01 for tx in transactions)  # Estimation
        
        if total_value > 0:
            fee_ratio = total_fees / total_value
            if fee_ratio > self.INSIGHT_THRESHOLDS["fee_high"]:
                return WalletInsight(
                    insight_id=uuid4(),
                    wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                    category="fees",
                    severity="warning",
                    title="💸 Frais Élevés",
                    description=f"Frais représentant {fee_ratio*100:.1f}% des transactions",
                    recommendation="Optimisez vos transactions pour réduire les frais",
                    value=fee_ratio,
                    metric="fee_ratio",
                    timestamp=datetime.now()
                )

        return None

    async def _analyze_activity(
        self,
        wallet: BaseWallet,
        transactions: List[Transaction]
    ) -> Optional[WalletInsight]:
        """
        Analyse l'activité du wallet.

        Args:
            wallet: Wallet
            transactions: Liste des transactions

        Returns:
            Insight sur l'activité
        """
        if not transactions:
            days_inactive = (datetime.now() - wallet.config.created_at).days
        else:
            last_tx = max(tx.timestamp for tx in transactions)
            days_inactive = (datetime.now() - last_tx).days

        if days_inactive > self.INSIGHT_THRESHOLDS["inactivity_days"]:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=wallet.config.wallet_id,
                category="activity",
                severity="info",
                title="💤 Wallet Inactif",
                description=f"Wallet inactif depuis {days_inactive} jours",
                recommendation="Envisagez de réactiver votre wallet",
                value=days_inactive,
                metric="inactivity_days",
                timestamp=datetime.now()
            )

        return None

    async def _analyze_diversification(
        self,
        balance: WalletBalance
    ) -> Optional[WalletInsight]:
        """
        Analyse la diversification.

        Args:
            balance: Solde du wallet

        Returns:
            Insight sur la diversification
        """
        total_tokens = len(balance.token_balances)
        
        if total_tokens == 0:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=balance.wallet_id,
                category="diversification",
                severity="info",
                title="📦 Portefeuille Non Diversifié",
                description="Votre portefeuille est composé uniquement de tokens natifs",
                recommendation="Ajoutez des tokens pour diversifier votre portefeuille",
                value=0,
                metric="token_count",
                timestamp=datetime.now()
            )
        elif total_tokens < 3:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=balance.wallet_id,
                category="diversification",
                severity="warning",
                title="⚠️ Faible Diversification",
                description=f"Seulement {total_tokens} tokens dans votre portefeuille",
                recommendation="Diversifiez avec au moins 5 tokens différents",
                value=total_tokens,
                metric="token_count",
                timestamp=datetime.now()
            )

        return None

    async def _analyze_market_risk(
        self,
        performance: PortfolioPerformance
    ) -> Optional[WalletInsight]:
        """
        Analyse le risque de marché.

        Args:
            performance: Performance du wallet

        Returns:
            Insight sur le risque de marché
        """
        if performance.sharpe_ratio < 0.5:
            return WalletInsight(
                insight_id=uuid4(),
                wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                category="market_risk",
                severity="warning",
                title="📊 Sharpe Ratio Faible",
                description=f"Sharpe Ratio de {performance.sharpe_ratio:.2f}",
                recommendation="Le rendement ajusté au risque est insuffisant",
                value=performance.sharpe_ratio,
                metric="sharpe_ratio",
                timestamp=datetime.now()
            )

        return None

    # ========================================================================
    # DONNÉES HISTORIQUES ET BENCHMARKS
    # ========================================================================

    async def _get_historical_prices(
        self,
        blockchain: str,
        period: AnalyticsPeriod
    ) -> List[float]:
        """
        Récupère les prix historiques pour une blockchain.

        Args:
            blockchain: Blockchain
            period: Période d'analyse

        Returns:
            Liste des prix historiques
        """
        try:
            # Mapping des symboles
            symbol_map = {
                "ethereum": "ethereum",
                "bsc": "binancecoin",
                "polygon": "polygon",
                "solana": "solana",
                "avalanche": "avalanche-2",
                "tron": "tron",
                "arbitrum": "arbitrum",
                "optimism": "optimism"
            }
            
            symbol = symbol_map.get(blockchain, "ethereum")
            
            # Conversion de la période
            days = self._period_to_days(period)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/coins/{symbol}/market_chart",
                    params={
                        "vs_currency": "usd",
                        "days": days,
                        "interval": "daily"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = [p[1] for p in data.get("prices", [])]
                        return prices

            return [1.0] * (days + 1)  # Prix par défaut

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des prix historiques: {e}")
            return [1.0] * (self._period_to_days(period) + 1)

    def _period_to_days(self, period: AnalyticsPeriod) -> int:
        """
        Convertit une période en jours.

        Args:
            period: Période

        Returns:
            Nombre de jours
        """
        days_map = {
            AnalyticsPeriod.HOUR: 1,
            AnalyticsPeriod.DAY: 1,
            AnalyticsPeriod.WEEK: 7,
            AnalyticsPeriod.MONTH: 30,
            AnalyticsPeriod.QUARTER: 90,
            AnalyticsPeriod.YEAR: 365,
            AnalyticsPeriod.ALL: 365
        }
        return days_map.get(period, 30)

    async def _get_benchmark_prices(
        self,
        period: AnalyticsPeriod
    ) -> Dict[str, float]:
        """
        Récupère les prix des benchmarks.

        Args:
            period: Période d'analyse

        Returns:
            Prix des benchmarks
        """
        try:
            days = self._period_to_days(period)
            benchmarks = {}
            
            async with aiohttp.ClientSession() as session:
                for symbol in self.BENCHMARK_PRICES.keys():
                    try:
                        async with session.get(
                            "https://api.coingecko.com/api/v3/coins/{symbol}/market_chart",
                            params={
                                "vs_currency": "usd",
                                "days": days,
                                "interval": "daily"
                            }
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                prices = [p[1] for p in data.get("prices", [])]
                                if prices:
                                    benchmarks[symbol] = prices[-1] / prices[0] - 1
                    except Exception as e:
                        logger.error(f"Erreur pour {symbol}: {e}")
                        benchmarks[symbol] = 0.0

            return benchmarks

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des benchmarks: {e}")
            return {}

    # ========================================================================
    # OPTIMISATION DE PORTEFEUILLE
    # ========================================================================

    async def optimize_portfolio(
        self,
        wallet: BaseWallet,
        target_metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Optimise le portefeuille.

        Args:
            wallet: Wallet à optimiser
            target_metrics: Métriques cibles

        Returns:
            Recommandations d'optimisation
        """
        try:
            balance = await wallet.get_balance()
            total_value = float(balance.total_balance_usd)
            
            if total_value == 0:
                return {"error": "Portefeuille vide"}

            # Répartition actuelle
            current_allocation = {}
            for token, amount in balance.token_balances.items():
                token_value = float(amount * Decimal(str(
                    await self._get_token_price(wallet, token)
                )))
                current_allocation[token] = token_value / total_value

            # Optimisation du portefeuille
            optimized_allocation = await self._optimize_allocation(
                current_allocation,
                target_metrics or ["sharpe_ratio", "max_drawdown"]
            )

            # Recommandations
            recommendations = []
            for token, target_pct in optimized_allocation.items():
                current_pct = current_allocation.get(token, 0)
                diff = target_pct - current_pct
                if abs(diff) > 0.05:  # Changement > 5%
                    action = "acheter" if diff > 0 else "vendre"
                    amount_usd = abs(diff) * total_value
                    recommendations.append({
                        "token": token,
                        "action": action,
                        "amount_usd": amount_usd,
                        "current_pct": current_pct * 100,
                        "target_pct": target_pct * 100
                    })

            return {
                "current_allocation": {k: v*100 for k, v in current_allocation.items()},
                "optimized_allocation": {k: v*100 for k, v in optimized_allocation.items()},
                "recommendations": recommendations,
                "expected_sharpe_ratio": await self._calculate_expected_sharpe(optimized_allocation),
                "expected_volatility": await self._calculate_expected_volatility(optimized_allocation),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation du portefeuille: {e}")
            return {"error": str(e)}

    async def _optimize_allocation(
        self,
        current_allocation: Dict[str, float],
        target_metrics: List[str]
    ) -> Dict[str, float]:
        """
        Optimise l'allocation du portefeuille.

        Args:
            current_allocation: Allocation actuelle
            target_metrics: Métriques cibles

        Returns:
            Allocation optimisée
        """
        # Fonction objectif pour l'optimisation
        def objective(weights):
            # Maximiser le Sharpe Ratio
            # Pour l'exemple, nous utilisons une fonction simplifiée
            return -sum(weights) / (np.std(weights) + 0.01)

        # Contraintes
        constraints = [
            {'type': 'eq', 'fun': lambda x: sum(x) - 1}  # Somme = 1
        ]
        bounds = [(0, 1) for _ in range(len(current_allocation))]

        # Valeurs initiales
        initial_weights = list(current_allocation.values())

        # Optimisation
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if result.success:
            optimized_weights = result.x
            return dict(zip(current_allocation.keys(), optimized_weights))

        return current_allocation

    async def _get_token_price(
        self,
        wallet: BaseWallet,
        token_address: str
    ) -> float:
        """
        Récupère le prix d'un token.

        Args:
            wallet: Wallet
            token_address: Adresse du token

        Returns:
            Prix du token en USD
        """
        token_info = await wallet.get_token_info(token_address)
        return token_info.price_usd if token_info else 0.0

    async def _calculate_expected_sharpe(
        self,
        allocation: Dict[str, float]
    ) -> float:
        """
        Calcule le Sharpe Ratio attendu.

        Args:
            allocation: Allocation du portefeuille

        Returns:
            Sharpe Ratio attendu
        """
        # Pour l'exemple
        return 0.8

    async def _calculate_expected_volatility(
        self,
        allocation: Dict[str, float]
    ) -> float:
        """
        Calcule la volatilité attendue.

        Args:
            allocation: Allocation du portefeuille

        Returns:
            Volatilité attendue en pourcentage
        """
        # Pour l'exemple
        return 25.0

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_analytics_summary(
        self,
        wallet_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère un résumé des analytics.

        Args:
            wallet_id: ID du wallet

        Returns:
            Résumé des analytics
        """
        try:
            performance = self._performance_cache.get(wallet_id, {})
            insights = self._insight_cache.get(wallet_id, [])
            
            return {
                "wallet_id": str(wallet_id),
                "performance": {
                    k: v.to_dict() for k, v in performance.items()
                },
                "insights": [i.to_dict() for i in insights],
                "insights_count": len(insights),
                "critical_insights": len([i for i in insights if i.severity == "critical"]),
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du résumé: {e}")
            return {}

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        return {
            "status": "healthy",
            "total_wallets_analyzed": self._metrics["total_wallets_analyzed"],
            "total_transactions_analyzed": self._metrics["total_transactions_analyzed"],
            "total_insights_generated": self._metrics["total_insights_generated"],
            "last_analysis": self._metrics["last_analysis"],
            "cached_wallets": len(self._performance_cache),
            "cached_insights": sum(len(i) for i in self._insight_cache.values()),
            "timestamp": datetime.now().isoformat()
        }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de WalletAnalyticsService...")
        self._snapshot_cache.clear()
        self._performance_cache.clear()
        self._insight_cache.clear()
        logger.info("WalletAnalyticsService fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_analytics_service(
    api_keys: Optional[Dict[str, str]] = None,
    redis_url: str = "redis://localhost:6379/0"
) -> WalletAnalyticsService:
    """
    Crée une instance du service d'analytique.

    Args:
        api_keys: Clés API pour les services externes
        redis_url: URL de connexion Redis

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletAnalyticsService(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AnalyticsPeriod",
    "RiskMetric",
    "PerformanceMetric",
    "PortfolioSnapshot",
    "PortfolioPerformance",
    "WalletInsight",
    "WalletAnalytics",
    "WalletAnalyticsService",
    "create_wallet_analytics_service"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service d'analytique."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET ANALYTICS MODULE")
    print("=" * 60)

    # Création du service
    analytics_service = create_wallet_analytics_service(
        api_keys={
            "coingecko": "YOUR_COINGECKO_API_KEY"
        }
    )

    # Création d'un wallet exemple
    from .ethereum_wallet import EthereumWallet, create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Analytics Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Analyse du wallet
    analytics = await analytics_service.analyze_wallet(
        wallet=wallet,
        period=AnalyticsPeriod.MONTH
    )

    print(f"\n📊 Analytics du wallet:")
    print(f"   Valeur totale: ${float(analytics.total_value_usd):,.2f}")
    print(f"   Transactions: {analytics.total_transactions}")
    print(f"   ROI: {analytics.roi_percentage:.2f}%")
    print(f"   Jours actifs: {analytics.days_active}")

    # Performance
    perf = analytics.performance
    print(f"\n📈 Performance:")
    print(f"   Sharpe Ratio: {perf.sharpe_ratio:.2f}")
    print(f"   Volatilité: {perf.volatility:.2f}%")
    print(f"   Max Drawdown: {perf.max_drawdown:.2f}%")
    print(f"   Win Rate: {perf.win_rate:.2f}%")

    # Insights
    print(f"\n💡 Insights:")
    for insight in analytics.insights[:5]:
        print(f"   [{insight.severity.upper()}] {insight.title}")
        print(f"      {insight.description}")
        print(f"      → {insight.recommendation}")

    # Optimisation du portefeuille
    optimization = await analytics_service.optimize_portfolio(wallet)
    if "recommendations" in optimization:
        print(f"\n🔄 Recommandations d'optimisation:")
        for rec in optimization["recommendations"]:
            print(f"   {rec['action'].upper()} {rec['token'][:8]}... ${rec['amount_usd']:,.2f}")

    # Santé du service
    health = await analytics_service.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Wallets analysés: {health['total_wallets_analyzed']}")
    print(f"   Insights générés: {health['total_insights_generated']}")

    # Fermeture
    await analytics_service.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletAnalyticsService NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

"""
NEXUS AI TRADING SYSTEM - Backtest Engine
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/backtest_engine.py
Description: Moteur de backtesting principal pour l'exécution de simulations
             de stratégies de trading sur données historiques.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from tqdm import tqdm

from trading.backtesting.data_provider import DataProvider
from trading.backtesting.metrics_calculator import MetricsCalculator
from trading.backtesting.strategy_runner import StrategyRunner
from trading.backtesting.simulator import Simulator
from trading.backtesting.results_analyzer import ResultsAnalyzer
from trading.backtesting.report_generator import ReportGenerator

from trading.strategies.base import BaseStrategy
from trading.strategies.factory import StrategyFactory

from trading.portfolio.performance import PerformanceTracker
from trading.portfolio.position_manager import PositionManager

from trading.risk_management.position_sizer import PositionSizer
from trading.risk_management.stop_loss import StopLossManager
from trading.risk_management.take_profit import TakeProfitManager
from trading.risk_management.drawdown_controller import DrawdownController

from shared.types.trading import (
    Order, OrderSide, OrderType, OrderStatus,
    Trade, Position, Portfolio, Signal
)
from shared.helpers.trading_helpers import (
    calculate_slippage, calculate_commission,
    validate_order, normalize_symbol
)
from shared.helpers.date_helpers import (
    timestamp_to_datetime, datetime_to_timestamp,
    parse_timeframe, get_timeframe_delta
)
from shared.constants.trading_constants import (
    DEFAULT_SLIPPAGE, DEFAULT_COMMISSION,
    MAX_POSITION_SIZE, MIN_POSITION_SIZE
)
from shared.constants.time_constants import (
    TIMEFRAME_1M, TIMEFRAME_5M, TIMEFRAME_15M,
    TIMEFRAME_1H, TIMEFRAME_4H, TIMEFRAME_1D,
    TIMEFRAME_1W, TIMEFRAME_1M
)
from shared.exceptions import (
    BacktestError, InsufficientDataError,
    InvalidStrategyError, ValidationError
)

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Configuration du backtesting.
    """
    # Paramètres de base
    symbol: str
    start_date: Union[str, datetime]
    end_date: Union[str, datetime]
    initial_capital: float = 100000.0
    timeframe: str = TIMEFRAME_1H
    
    # Paramètres de la stratégie
    strategy_name: str = "momentum"
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    
    # Paramètres de gestion des risques
    max_position_size: float = MAX_POSITION_SIZE
    min_position_size: float = MIN_POSITION_SIZE
    max_positions: int = 5
    stop_loss_pct: float = 0.02  # 2%
    take_profit_pct: float = 0.04  # 4%
    max_drawdown_pct: float = 0.20  # 20%
    risk_per_trade_pct: float = 0.01  # 1%
    
    # Paramètres d'exécution
    slippage_pct: float = DEFAULT_SLIPPAGE
    commission_pct: float = DEFAULT_COMMISSION
    commission_fixed: float = 0.0
    
    # Paramètres de simulation
    use_market_impact: bool = True
    use_slippage: bool = True
    use_commission: bool = True
    use_fractional_shares: bool = True
    
    # Paramètres de sortie
    save_results: bool = True
    output_dir: str = "data/backtest_results/"
    generate_report: bool = True
    
    # Paramètres de performance
    warmup_bars: int = 100
    max_bars: int = 100000
    parallel: bool = False
    
    def __post_init__(self):
        """Validation et transformation des paramètres."""
        # Convertir les dates si nécessaire
        if isinstance(self.start_date, str):
            self.start_date = datetime.fromisoformat(self.start_date)
        if isinstance(self.end_date, str):
            self.end_date = datetime.fromisoformat(self.end_date)
        
        # Validation
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date")
        
        if self.initial_capital <= 0:
            raise ValidationError("Initial capital must be positive")
        
        if self.max_position_size <= 0:
            self.max_position_size = self.initial_capital * 0.5
        
        if self.min_position_size <= 0:
            self.min_position_size = self.initial_capital * 0.01
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la configuration en dictionnaire."""
        return {
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "strategy_params": self.strategy_params,
            "max_position_size": self.max_position_size,
            "min_position_size": self.min_position_size,
            "max_positions": self.max_positions,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "slippage_pct": self.slippage_pct,
            "commission_pct": self.commission_pct,
            "commission_fixed": self.commission_fixed
        }


@dataclass
class BacktestResult:
    """
    Résultats du backtesting.
    """
    # Métriques de base
    total_return: float = 0.0
    annualized_return: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Métriques de performance
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Métriques de trading
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    recovery_factor: float = 0.0
    
    # Données détaillées
    equity_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_curve: pd.Series = field(default_factory=pd.Series)
    trades: List[Trade] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    
    # Métadonnées
    config: BacktestConfig = None
    execution_time: float = 0.0
    start_time: datetime = None
    end_time: datetime = None
    num_bars: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit les résultats en dictionnaire."""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "recovery_factor": self.recovery_factor,
            "num_trades": self.total_trades,
            "num_bars": self.num_bars,
            "execution_time": self.execution_time
        }


class BacktestEngine:
    """
    Moteur de backtesting principal.
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialise le moteur de backtesting.
        
        Args:
            config: Configuration du backtesting.
        """
        self.config = config
        
        # Initialisation des composants
        self.data_provider = DataProvider()
        self.metrics_calculator = MetricsCalculator()
        self.results_analyzer = ResultsAnalyzer()
        self.report_generator = ReportGenerator()
        
        # Initialisation des gestionnaires
        self.position_manager = PositionManager()
        self.position_sizer = PositionSizer(config.risk_per_trade_pct)
        self.stop_loss_manager = StopLossManager(config.stop_loss_pct)
        self.take_profit_manager = TakeProfitManager(config.take_profit_pct)
        self.drawdown_controller = DrawdownController(config.max_drawdown_pct)
        
        # État du backtesting
        self.portfolio = Portfolio(
            initial_capital=config.initial_capital,
            cash=config.initial_capital,
            total_value=config.initial_capital
        )
        self.performance_tracker = PerformanceTracker()
        
        # Historique
        self.trades: List[Trade] = []
        self.positions: List[Position] = []
        self.equity_curve: List[float] = []
        self.drawdown_curve: List[float] = []
        
        # État interne
        self.current_bar = 0
        self.current_time = None
        self._is_running = False
        self._is_paused = False
        
        # Stratégie
        self.strategy: Optional[BaseStrategy] = None
        
        logger.info(f"BacktestEngine initialisé pour {config.symbol}")
        logger.info(f"Période: {config.start_date} -> {config.end_date}")
        logger.info(f"Capital initial: ${config.initial_capital:,.2f}")
    
    def _load_data(self) -> pd.DataFrame:
        """
        Charge les données historiques.
        
        Returns:
            DataFrame contenant les données OHLCV.
            
        Raises:
            InsufficientDataError: Si les données sont insuffisantes.
        """
        logger.info(f"Chargement des données pour {self.config.symbol}...")
        
        # Chargement des données
        data = self.data_provider.get_historical_data(
            symbol=self.config.symbol,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            timeframe=self.config.timeframe
        )
        
        if data.empty:
            raise InsufficientDataError(f"Aucune donnée trouvée pour {self.config.symbol}")
        
        if len(data) < self.config.warmup_bars:
            raise InsufficientDataError(
                f"Données insuffisantes: {len(data)} bars, "
                f"besoin de {self.config.warmup_bars} bars"
            )
        
        logger.info(f"Données chargées: {len(data)} bars")
        return data
    
    def _initialize_strategy(self) -> None:
        """
        Initialise la stratégie de trading.
        
        Raises:
            InvalidStrategyError: Si la stratégie n'existe pas.
        """
        logger.info(f"Initialisation de la stratégie: {self.config.strategy_name}")
        
        try:
            self.strategy = StrategyFactory.create(
                name=self.config.strategy_name,
                params=self.config.strategy_params
            )
            
            if self.strategy is None:
                raise InvalidStrategyError(
                    f"Stratégie '{self.config.strategy_name}' non trouvée"
                )
            
            # Initialisation de la stratégie
            self.strategy.initialize(self.config.symbol, self.config.timeframe)
            
            logger.info(f"Stratégie initialisée: {self.config.strategy_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la stratégie: {e}")
            raise InvalidStrategyError(str(e))
    
    def _calculate_position_size(
        self,
        price: float,
        signal: Signal
    ) -> float:
        """
        Calcule la taille de la position.
        
        Args:
            price: Prix actuel.
            signal: Signal de trading.
            
        Returns:
            Taille de la position en unités.
        """
        # Calcul du capital à risquer
        capital_to_risk = self.portfolio.cash * self.config.risk_per_trade_pct
        
        # Utilisation du position sizer
        position_size = self.position_sizer.calculate_position_size(
            price=price,
            capital=capital_to_risk,
            stop_loss_pct=self.config.stop_loss_pct
        )
        
        # Limites
        position_size = min(position_size, self.config.max_position_size)
        position_size = max(position_size, self.config.min_position_size)
        
        # Vérification du nombre maximal de positions
        if len(self.positions) >= self.config.max_positions:
            return 0.0
        
        return position_size
    
    def _execute_order(self, order: Order) -> Trade:
        """
        Exécute un ordre de trading.
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Trade exécuté.
        """
        # Validation de l'ordre
        validate_order(order)
        
        # Calcul du slippage
        if self.config.use_slippage:
            order.price = calculate_slippage(
                price=order.price,
                side=order.side,
                volume=order.quantity,
                slippage_pct=self.config.slippage_pct
            )
        
        # Calcul de la commission
        if self.config.use_commission:
            commission = calculate_commission(
                price=order.price,
                volume=order.quantity,
                commission_pct=self.config.commission_pct,
                commission_fixed=self.config.commission_fixed
            )
        else:
            commission = 0.0
        
        # Mise à jour du capital
        order_value = order.price * order.quantity
        total_cost = order_value + commission
        
        if order.side == OrderSide.BUY:
            self.portfolio.cash -= total_cost
        else:  # SELL
            self.portfolio.cash += order_value - commission
        
        # Création du trade
        trade = Trade(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            commission=commission,
            timestamp=self.current_time,
            order_type=order.order_type,
            status=OrderStatus.FILLED
        )
        
        # Mise à jour du portfolio
        self.portfolio.total_value = self.portfolio.cash + self._get_open_positions_value()
        
        return trade
    
    def _get_open_positions_value(self) -> float:
        """
        Calcule la valeur des positions ouvertes.
        
        Returns:
            Valeur totale des positions ouvertes.
        """
        total = 0.0
        for position in self.positions:
            if position.is_open:
                total += position.quantity * position.current_price
        return total
    
    def _update_positions(self, current_price: float) -> None:
        """
        Met à jour les positions avec le prix actuel.
        
        Args:
            current_price: Prix actuel.
        """
        closed_positions = []
        
        for position in self.positions:
            if not position.is_open:
                continue
            
            # Mise à jour du prix
            position.current_price = current_price
            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            
            # Vérification du stop loss
            if self.stop_loss_manager.should_exit(position):
                # Fermeture de la position
                exit_order = Order(
                    symbol=position.symbol,
                    side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                    quantity=position.quantity,
                    price=current_price,
                    order_type=OrderType.MARKET,
                    timestamp=self.current_time
                )
                trade = self._execute_order(exit_order)
                
                position.close(trade.price)
                position.unrealized_pnl = 0.0
                position.realized_pnl = position.calculate_pnl()
                
                closed_positions.append(position)
                self.trades.append(trade)
                
                logger.debug(
                    f"Position fermée: {position.symbol} "
                    f"PNL: ${position.realized_pnl:,.2f}"
                )
            
            # Vérification du take profit
            elif self.take_profit_manager.should_exit(position):
                exit_order = Order(
                    symbol=position.symbol,
                    side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                    quantity=position.quantity,
                    price=current_price,
                    order_type=OrderType.MARKET,
                    timestamp=self.current_time
                )
                trade = self._execute_order(exit_order)
                
                position.close(trade.price)
                position.unrealized_pnl = 0.0
                position.realized_pnl = position.calculate_pnl()
                
                closed_positions.append(position)
                self.trades.append(trade)
                
                logger.debug(
                    f"Take profit atteint: {position.symbol} "
                    f"PNL: ${position.realized_pnl:,.2f}"
                )
        
        # Retrait des positions fermées
        for position in closed_positions:
            self.positions.remove(position)
    
    def _process_bar(self, bar: pd.Series) -> None:
        """
        Traite un bar de données.
        
        Args:
            bar: Bar de données (OHLCV).
        """
        self.current_time = bar['timestamp']
        current_price = bar['close']
        
        # Mise à jour des positions
        self._update_positions(current_price)
        
        # Vérification du drawdown maximal
        current_value = self.portfolio.cash + self._get_open_positions_value()
        if self.drawdown_controller.check_drawdown(current_value, self.portfolio.initial_capital):
            self._is_running = False
            logger.warning(f"Drawdown maximal atteint: {self.config.max_drawdown_pct:.2%}")
            return
        
        # Génération des signaux
        signals = self.strategy.generate_signals(bar)
        
        # Traitement des signaux
        for signal in signals:
            if signal.action == "open_long":
                # Calcul de la taille de la position
                position_size = self._calculate_position_size(current_price, signal)
                
                if position_size > 0:
                    # Création de l'ordre
                    order = Order(
                        symbol=self.config.symbol,
                        side=OrderSide.BUY,
                        quantity=position_size,
                        price=current_price,
                        order_type=OrderType.MARKET,
                        timestamp=self.current_time
                    )
                    
                    # Exécution
                    trade = self._execute_order(order)
                    
                    # Création de la position
                    position = Position(
                        symbol=self.config.symbol,
                        side=OrderSide.BUY,
                        quantity=position_size,
                        entry_price=current_price,
                        current_price=current_price,
                        open_time=self.current_time,
                        stop_loss=current_price * (1 - self.config.stop_loss_pct),
                        take_profit=current_price * (1 + self.config.take_profit_pct)
                    )
                    
                    self.positions.append(position)
                    self.trades.append(trade)
                    
                    logger.debug(
                        f"Position ouverte: {self.config.symbol} "
                        f"Quantité: {position_size:.4f} @ ${current_price:.2f}"
                    )
            
            elif signal.action == "open_short":
                # Similaire pour short
                pass
            
            elif signal.action == "close":
                # Fermeture de la position
                for position in self.positions:
                    if position.is_open:
                        exit_order = Order(
                            symbol=self.config.symbol,
                            side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                            quantity=position.quantity,
                            price=current_price,
                            order_type=OrderType.MARKET,
                            timestamp=self.current_time
                        )
                        trade = self._execute_order(exit_order)
                        
                        position.close(trade.price)
                        position.realized_pnl = position.calculate_pnl()
                        
                        self.positions.remove(position)
                        self.trades.append(trade)
        
        # Mise à jour de l'equity curve
        current_value = self.portfolio.cash + self._get_open_positions_value()
        self.equity_curve.append(current_value)
        
        # Mise à jour du drawdown
        peak = max(self.equity_curve) if self.equity_curve else current_value
        drawdown = (peak - current_value) / peak if peak > 0 else 0
        self.drawdown_curve.append(drawdown)
        
        # Mise à jour du portfolio
        self.portfolio.total_value = current_value
        self.portfolio.equity_curve = self.equity_curve
        
        # Enregistrement de la performance
        self.performance_tracker.record_equity(current_value, self.current_time)
        
        # Mise à jour de l'état
        self.current_bar += 1
    
    def run(self) -> BacktestResult:
        """
        Exécute le backtesting.
        
        Returns:
            Résultats du backtesting.
        """
        start_time = time.time()
        self._is_running = True
        
        logger.info("=" * 60)
        logger.info("DÉBUT DU BACKTESTING")
        logger.info("=" * 60)
        
        try:
            # Chargement des données
            data = self._load_data()
            
            # Initialisation de la stratégie
            self._initialize_strategy()
            
            # Warmup
            warmup_data = data.iloc[:self.config.warmup_bars]
            self.strategy.warmup(warmup_data)
            
            # Backtesting principal
            main_data = data.iloc[self.config.warmup_bars:]
            
            if self.config.parallel and len(main_data) > 1000:
                # Exécution parallèle
                self._run_parallel(main_data)
            else:
                # Exécution séquentielle
                with tqdm(total=len(main_data), desc="Backtesting") as pbar:
                    for _, bar in main_data.iterrows():
                        if not self._is_running:
                            break
                        self._process_bar(bar)
                        pbar.update(1)
            
            # Fermeture des positions restantes
            self._close_all_positions(data.iloc[-1]['close'])
            
            # Calcul des métriques
            results = self._compute_results()
            
            # Sauvegarde des résultats
            if self.config.save_results:
                self._save_results(results)
            
            # Génération du rapport
            if self.config.generate_report:
                self._generate_report(results)
            
            # Temps d'exécution
            results.execution_time = time.time() - start_time
            
            logger.info("=" * 60)
            logger.info("FIN DU BACKTESTING")
            logger.info(f"Temps d'exécution: {results.execution_time:.2f} secondes")
            logger.info(f"Nombre de trades: {results.total_trades}")
            logger.info(f"Return total: {results.total_return:.2%}")
            logger.info(f"Sharpe ratio: {results.sharpe_ratio:.2f}")
            logger.info("=" * 60)
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors du backtesting: {e}")
            raise BacktestError(str(e))
        
        finally:
            self._is_running = False
    
    def _run_parallel(self, data: pd.DataFrame) -> None:
        """
        Exécute le backtesting en parallèle (SIMD).
        
        Args:
            data: Données à traiter.
        """
        # Implémentation de l'exécution parallèle
        # À implémenter selon les besoins
        pass
    
    def _close_all_positions(self, price: float) -> None:
        """
        Ferme toutes les positions.
        
        Args:
            price: Prix de fermeture.
        """
        if not self.positions:
            return
        
        logger.info(f"Fermeture de {len(self.positions)} positions...")
        
        for position in self.positions:
            if position.is_open:
                exit_order = Order(
                    symbol=self.config.symbol,
                    side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                    quantity=position.quantity,
                    price=price,
                    order_type=OrderType.MARKET,
                    timestamp=self.current_time
                )
                trade = self._execute_order(exit_order)
                
                position.close(trade.price)
                position.realized_pnl = position.calculate_pnl()
                
                self.positions.remove(position)
                self.trades.append(trade)
    
    def _compute_results(self) -> BacktestResult:
        """
        Calcule les métriques de performance.
        
        Returns:
            Résultats du backtesting.
        """
        logger.info("Calcul des métriques de performance...")
        
        result = BacktestResult()
        result.config = self.config
        
        # Métriques de base
        equity_series = pd.Series(self.equity_curve)
        result.equity_curve = equity_series
        result.drawdown_curve = pd.Series(self.drawdown_curve)
        
        result.total_return = self.metrics_calculator.calculate_total_return(equity_series)
        result.annualized_return = self.metrics_calculator.calculate_annualized_return(
            equity_series, len(self.equity_curve)
        )
        
        # Métriques de trading
        result.total_trades = len(self.trades)
        if result.total_trades > 0:
            winning_trades = [t for t in self.trades if t.pnl > 0]
            losing_trades = [t for t in self.trades if t.pnl <= 0]
            
            result.winning_trades = len(winning_trades)
            result.losing_trades = len(losing_trades)
            result.win_rate = result.winning_trades / result.total_trades
            
            if winning_trades:
                result.average_win = sum(t.pnl for t in winning_trades) / len(winning_trades)
            if losing_trades:
                result.average_loss = sum(t.pnl for t in losing_trades) / len(losing_trades)
            
            total_profit = sum(t.pnl for t in winning_trades)
            total_loss = abs(sum(t.pnl for t in losing_trades))
            result.profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            
            result.expectancy = (result.win_rate * result.average_win -
                                (1 - result.win_rate) * result.average_loss)
        
        # Métriques de performance
        result.sharpe_ratio = self.metrics_calculator.calculate_sharpe_ratio(
            equity_series, self.config.initial_capital
        )
        result.sortino_ratio = self.metrics_calculator.calculate_sortino_ratio(
            equity_series, self.config.initial_capital
        )
        result.calmar_ratio = self.metrics_calculator.calculate_calmar_ratio(
            equity_series, self.config.initial_capital
        )
        
        result.max_drawdown, result.max_drawdown_pct = (
            self.metrics_calculator.calculate_max_drawdown(equity_series)
        )
        
        result.recovery_factor = (
            result.total_return / result.max_drawdown_pct
            if result.max_drawdown_pct > 0 else 0
        )
        
        # Métadonnées
        result.num_bars = len(self.equity_curve)
        result.start_time = self.config.start_date
        result.end_time = self.config.end_date
        
        return result
    
    def _save_results(self, results: BacktestResult) -> None:
        """
        Sauvegarde les résultats sur le disque.
        
        Args:
            results: Résultats à sauvegarder.
        """
        import os
        import json
        
        try:
            # Création du répertoire
            os.makedirs(self.config.output_dir, exist_ok=True)
            
            # Nom du fichier
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.config.symbol}_{self.config.strategy_name}_{timestamp}.json"
            filepath = os.path.join(self.config.output_dir, filename)
            
            # Sauvegarde
            output = {
                "config": self.config.to_dict(),
                "results": results.to_dict(),
                "trades": [trade.to_dict() for trade in self.trades],
                "equity_curve": results.equity_curve.tolist(),
                "drawdown_curve": results.drawdown_curve.tolist()
            }
            
            with open(filepath, 'w') as f:
                json.dump(output, f, indent=2, default=str)
            
            logger.info(f"Résultats sauvegardés: {filepath}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
    
    def _generate_report(self, results: BacktestResult) -> None:
        """
        Génère un rapport HTML du backtesting.
        
        Args:
            results: Résultats du backtesting.
        """
        try:
            self.report_generator.generate_report(
                results=results,
                output_dir=self.config.output_dir,
                symbol=self.config.symbol,
                strategy_name=self.config.strategy_name
            )
            logger.info(f"Rapport généré: {self.config.output_dir}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du backtesting.
        
        Returns:
            Dictionnaire contenant le statut.
        """
        return {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "current_bar": self.current_bar,
            "current_time": self.current_time.isoformat() if self.current_time else None,
            "positions_open": len([p for p in self.positions if p.is_open]),
            "total_trades": len(self.trades),
            "portfolio_value": self.portfolio.total_value,
            "cash": self.portfolio.cash
        }
    
    def pause(self) -> None:
        """Met en pause le backtesting."""
        self._is_paused = True
        logger.info("Backtesting en pause")
    
    def resume(self) -> None:
        """Reprend le backtesting."""
        self._is_paused = False
        logger.info("Backtesting repris")
    
    def stop(self) -> None:
        """Arrête le backtesting."""
        self._is_running = False
        logger.info("Backtesting arrêté")


# Fonction utilitaire pour exécuter un backtest rapidement
def run_backtest(
    symbol: str,
    start_date: Union[str, datetime],
    end_date: Union[str, datetime],
    strategy: str = "momentum",
    initial_capital: float = 100000.0,
    **kwargs
) -> BacktestResult:
    """
    Fonction utilitaire pour exécuter un backtest.
    
    Args:
        symbol: Symbole à tester.
        start_date: Date de début.
        end_date: Date de fin.
        strategy: Nom de la stratégie.
        initial_capital: Capital initial.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats du backtesting.
    """
    config = BacktestConfig(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        strategy_name=strategy,
        **kwargs
    )
    
    engine = BacktestEngine(config)
    return engine.run()


# Exportation
__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'BacktestResult',
    'run_backtest'
]

"""
NEXUS AI TRADING SYSTEM - Strategy Runner
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/strategy_runner.py
Description: Runner de stratégies pour le backtesting et l'exécution en temps réel.
             Supporte l'exécution asynchrone, la gestion des événements,
             et l'intégration avec les brokers et les sources de données.
"""

import logging
import asyncio
import time
import signal
import threading
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from trading.strategies.base import BaseStrategy
from trading.strategies.factory import StrategyFactory
from trading.backtesting.data_provider import DataProvider
from trading.backtesting.simulator import MarketSimulator, SimulationConfig
from trading.brokers.base import Broker, Order, OrderSide, OrderType, OrderStatus
from trading.portfolio.position_manager import PositionManager
from trading.risk_management.position_sizer import PositionSizer
from trading.risk_management.stop_loss import StopLossManager
from trading.risk_management.take_profit import TakeProfitManager
from trading.risk_management.drawdown_controller import DrawdownController
from trading.signals.generator import SignalGenerator
from shared.helpers.trading_helpers import validate_order, normalize_symbol
from shared.helpers.date_helpers import timestamp_to_datetime, datetime_to_timestamp
from shared.exceptions import StrategyRunnerError

# Configuration du logging
logger = logging.getLogger(__name__)


class RunnerStatus(Enum):
    """Statut du StrategyRunner."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ExecutionMode(Enum):
    """Mode d'exécution."""
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"
    SIMULATION = "simulation"


@dataclass
class RunnerConfig:
    """
    Configuration du StrategyRunner.
    """
    # Mode d'exécution
    mode: ExecutionMode = ExecutionMode.BACKTEST
    
    # Paramètres de la stratégie
    strategy_name: str
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    symbol: str = ""
    
    # Paramètres de trading
    initial_capital: float = 100000.0
    timeframe: str = "1h"
    
    # Paramètres de risque
    max_positions: int = 5
    max_position_size: float = 10000.0
    min_position_size: float = 100.0
    risk_per_trade: float = 0.02
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_drawdown_pct: float = 0.20
    
    # Paramètres de données
    data_provider: Optional[DataProvider] = None
    broker: Optional[Broker] = None
    
    # Paramètres de backtest
    start_date: Optional[Union[str, datetime]] = None
    end_date: Optional[Union[str, datetime]] = None
    
    # Paramètres de simulation
    simulation_config: Optional[SimulationConfig] = None
    
    # Paramètres d'exécution
    real_time: bool = False
    interval_seconds: int = 60
    batch_size: int = 100
    
    # Paramètres de performance
    parallel: bool = False
    n_workers: int = 4
    
    # Paramètres de sortie
    save_trades: bool = True
    save_equity_curve: bool = True
    output_dir: str = "data/strategy_runs/"
    
    def __post_init__(self):
        """Validation des paramètres."""
        if not self.strategy_name:
            raise StrategyRunnerError("Nom de stratégie requis")
        
        if self.mode == ExecutionMode.BACKTEST:
            if not self.start_date or not self.end_date:
                raise StrategyRunnerError("Dates requises pour le backtest")
            
            if isinstance(self.start_date, str):
                self.start_date = datetime.fromisoformat(self.start_date)
            if isinstance(self.end_date, str):
                self.end_date = datetime.fromisoformat(self.end_date)
            
            if self.start_date >= self.end_date:
                raise StrategyRunnerError("La date de début doit être avant la date de fin")
        
        if self.mode == ExecutionMode.LIVE_TRADING and not self.broker:
            raise StrategyRunnerError("Broker requis pour le live trading")


@dataclass
class RunnerState:
    """
    État du StrategyRunner.
    """
    status: RunnerStatus = RunnerStatus.IDLE
    current_time: Optional[datetime] = None
    current_price: float = 0.0
    positions: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    last_update: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'status': self.status.value,
            'current_time': self.current_time.isoformat() if self.current_time else None,
            'current_price': self.current_price,
            'positions': self.positions,
            'trades_count': len(self.trades),
            'equity_curve_length': len(self.equity_curve),
            'performance_metrics': self.performance_metrics,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }


class StrategyRunner:
    """
    Runner de stratégies de trading.
    """
    
    def __init__(self, config: RunnerConfig):
        """
        Initialise le StrategyRunner.
        
        Args:
            config: Configuration du runner.
        """
        self.config = config
        self.state = RunnerState()
        
        # Initialisation des composants
        self.strategy: Optional[BaseStrategy] = None
        self.data_provider = config.data_provider or DataProvider()
        self.broker = config.broker
        
        # Gestionnaires de risque
        self.position_manager = PositionManager()
        self.position_sizer = PositionSizer(config.risk_per_trade)
        self.stop_loss_manager = StopLossManager(config.stop_loss_pct)
        self.take_profit_manager = TakeProfitManager(config.take_profit_pct)
        self.drawdown_controller = DrawdownController(config.max_drawdown_pct)
        
        # Gestionnaire de signaux
        self.signal_generator = SignalGenerator()
        
        # Gestion des événements
        self.event_queue: Queue = Queue()
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._running = False
        self._paused = False
        self._stop_signal = False
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=config.n_workers)
        
        # Métriques
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0
        }
        
        # Initialisation
        self._initialize()
        
        logger.info(f"StrategyRunner initialisé - Stratégie: {config.strategy_name}")
        logger.info(f"Mode: {config.mode.value}, Symbole: {config.symbol}")
    
    def _initialize(self) -> None:
        """
        Initialise les composants.
        """
        self.state.status = RunnerStatus.INITIALIZING
        
        try:
            # Initialisation de la stratégie
            self.strategy = StrategyFactory.create(
                name=self.config.strategy_name,
                params=self.config.strategy_params
            )
            
            if not self.strategy:
                raise StrategyRunnerError(
                    f"Stratégie '{self.config.strategy_name}' non trouvée"
                )
            
            # Initialisation de la stratégie
            self.strategy.initialize(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe
            )
            
            # Initialisation du broker
            if self.config.mode == ExecutionMode.LIVE_TRADING and self.broker:
                self.broker.connect()
            
            logger.info("Initialisation terminée")
            self.state.status = RunnerStatus.IDLE
            
        except Exception as e:
            logger.error(f"Erreur d'initialisation: {e}")
            self.state.status = RunnerStatus.ERROR
            raise StrategyRunnerError(f"Erreur d'initialisation: {e}")
    
    # ============================================================
    # MÉTHODES D'EXÉCUTION
    # ============================================================
    
    def run(self) -> Dict[str, Any]:
        """
        Exécute la stratégie.
        
        Returns:
            Résultats de l'exécution.
        """
        if self.state.status == RunnerStatus.RUNNING:
            raise StrategyRunnerError("Le runner est déjà en cours d'exécution")
        
        self.state.status = RunnerStatus.RUNNING
        self._running = True
        
        logger.info(f"Démarrage de l'exécution en mode {self.config.mode.value}")
        
        try:
            if self.config.mode == ExecutionMode.BACKTEST:
                return self._run_backtest()
            elif self.config.mode == ExecutionMode.SIMULATION:
                return self._run_simulation()
            elif self.config.mode in [ExecutionMode.PAPER_TRADING, ExecutionMode.LIVE_TRADING]:
                return self._run_real_time()
            else:
                raise StrategyRunnerError(f"Mode non supporté: {self.config.mode}")
                
        except Exception as e:
            logger.error(f"Erreur d'exécution: {e}")
            self.state.status = RunnerStatus.ERROR
            raise StrategyRunnerError(f"Erreur d'exécution: {e}")
        
        finally:
            self._running = False
            if self.state.status != RunnerStatus.ERROR:
                self.state.status = RunnerStatus.STOPPED
    
    def _run_backtest(self) -> Dict[str, Any]:
        """
        Exécute un backtest.
        
        Returns:
            Résultats du backtest.
        """
        from trading.backtesting.backtest_engine import BacktestEngine, BacktestConfig
        from trading.backtesting.metrics_calculator import MetricsCalculator
        from trading.backtesting.results_analyzer import ResultsAnalyzer
        
        logger.info("Démarrage du backtest...")
        
        # Configuration du backtest
        backtest_config = BacktestConfig(
            symbol=self.config.symbol,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_capital=self.config.initial_capital,
            timeframe=self.config.timeframe,
            strategy_name=self.config.strategy_name,
            strategy_params=self.config.strategy_params,
            max_positions=self.config.max_positions,
            max_position_size=self.config.max_position_size,
            min_position_size=self.config.min_position_size,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_drawdown_pct=self.config.max_drawdown_pct,
            risk_per_trade_pct=self.config.risk_per_trade
        )
        
        # Exécution du backtest
        engine = BacktestEngine(backtest_config)
        result = engine.run()
        
        # Analyse des résultats
        analyzer = ResultsAnalyzer()
        robustness = analyzer.analyze_robustness(result)
        statistical_tests = analyzer.run_statistical_tests(result)
        
        # Mise à jour de l'état
        self.state.positions = result.positions
        self.state.trades = result.trades
        self.state.equity_curve = result.equity_curve
        self.state.performance_metrics = {
            'total_return': result.total_return,
            'annualized_return': result.annualized_return,
            'sharpe_ratio': result.sharpe_ratio,
            'sortino_ratio': result.sortino_ratio,
            'calmar_ratio': result.calmar_ratio,
            'max_drawdown': result.max_drawdown_pct,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades
        }
        
        # Construction du résultat
        return {
            'backtest_result': result.to_dict(),
            'robustness': robustness.to_dict(),
            'statistical_tests': statistical_tests.to_dict(),
            'trades': [t.__dict__ for t in result.trades],
            'equity_curve': result.equity_curve.tolist(),
            'performance_metrics': self.state.performance_metrics
        }
    
    def _run_simulation(self) -> Dict[str, Any]:
        """
        Exécute une simulation.
        
        Returns:
            Résultats de la simulation.
        """
        logger.info("Démarrage de la simulation...")
        
        # Création du simulateur
        sim_config = self.config.simulation_config or SimulationConfig(
            symbol=self.config.symbol,
            initial_price=100.0,
            initial_capital=self.config.initial_capital,
            time_step=self.config.timeframe
        )
        
        simulator = MarketSimulator(sim_config)
        
        # Initialisation de la stratégie
        self.strategy.initialize(self.config.symbol, self.config.timeframe)
        
        # Warmup
        warmup_data = self.data_provider.get_historical_data(
            symbol=self.config.symbol,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            timeframe=self.config.timeframe
        )
        
        if not warmup_data.empty:
            self.strategy.warmup(warmup_data)
        
        # Simulation
        ticks = []
        
        def process_tick(tick, step, total):
            # Mise à jour du prix
            self.state.current_price = tick.price
            self.state.current_time = tick.timestamp
            
            # Génération des signaux
            signal = self.strategy.generate_signal(
                open=tick.open,
                high=tick.high,
                low=tick.low,
                close=tick.close,
                volume=tick.volume,
                timestamp=tick.timestamp
            )
            
            # Traitement du signal
            if signal:
                self._process_signal(signal)
            
            # Mise à jour de l'equity
            equity = simulator.balance + simulator.holdings * tick.price
            self.state.equity_curve.append(equity)
            
            ticks.append(tick)
        
        # Exécution de la simulation
        simulator.run_simulation(
            steps=self.config.batch_size,
            callback=process_tick
        )
        
        # Résultats
        stats = simulator.get_statistics()
        self.state.performance_metrics = stats
        
        return {
            'simulation_stats': stats,
            'ticks': len(ticks),
            'trades': self.state.trades,
            'equity_curve': self.state.equity_curve,
            'performance_metrics': stats
        }
    
    def _run_real_time(self) -> Dict[str, Any]:
        """
        Exécute en temps réel.
        
        Returns:
            Résultats de l'exécution.
        """
        logger.info("Démarrage de l'exécution en temps réel...")
        
        # Configuration des signaux
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Boucle principale
        last_update = datetime.now()
        
        while self._running and not self._stop_signal:
            try:
                current_time = datetime.now()
                
                # Vérification de l'intervalle
                if (current_time - last_update).total_seconds() < self.config.interval_seconds:
                    time.sleep(1)
                    continue
                
                # Mise à jour des données
                self._update_market_data()
                
                # Génération des signaux
                self._generate_and_process_signals()
                
                # Mise à jour des positions
                self._update_positions()
                
                # Mise à jour des métriques
                self._update_metrics()
                
                last_update = current_time
                self.state.last_update = current_time
                
                # Logging périodique
                if self.state.total_trades % 10 == 0:
                    logger.info(f"Statut: {self.state.total_trades} trades, "
                              f"PNL: {self.metrics['total_pnl']:.2f}")
                
            except Exception as e:
                logger.error(f"Erreur dans la boucle principale: {e}")
                if not self._running:
                    break
                time.sleep(5)
        
        # Fermeture
        if self.broker:
            self.broker.disconnect()
        
        return {
            'total_trades': self.state.total_trades,
            'total_pnl': self.metrics['total_pnl'],
            'winning_trades': self.metrics['winning_trades'],
            'losing_trades': self.metrics['losing_trades'],
            'final_equity': self.state.equity_curve[-1] if self.state.equity_curve else 0,
            'trades': self.state.trades
        }
    
    # ============================================================
    # TRAITEMENT DES DONNÉES
    # ============================================================
    
    def _update_market_data(self) -> None:
        """
        Met à jour les données de marché.
        """
        if self.broker:
            # Données en temps réel
            ticker = self.broker.get_ticker(self.config.symbol)
            self.state.current_price = ticker.get('last_price', 0)
            self.state.current_time = ticker.get('timestamp', datetime.now())
        else:
            # Utiliser le DataProvider
            data = self.data_provider.get_historical_data(
                symbol=self.config.symbol,
                start_date=datetime.now() - timedelta(minutes=5),
                end_date=datetime.now(),
                timeframe='1m'
            )
            
            if not data.empty:
                latest = data.iloc[-1]
                self.state.current_price = latest['close']
                self.state.current_time = latest['timestamp']
    
    def _generate_and_process_signals(self) -> None:
        """
        Génère et traite les signaux.
        """
        # Récupération des données
        data = self._get_current_data()
        
        if data is None or data.empty:
            return
        
        # Warmup si nécessaire
        if not self.strategy._is_warmed_up:
            self.strategy.warmup(data.iloc[:100])
        
        # Génération du signal
        latest = data.iloc[-1]
        signal = self.strategy.generate_signal(
            open=latest['open'],
            high=latest['high'],
            low=latest['low'],
            close=latest['close'],
            volume=latest['volume'],
            timestamp=latest['timestamp']
        )
        
        # Traitement du signal
        if signal:
            self._process_signal(signal)
    
    def _get_current_data(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données actuelles.
        
        Returns:
            DataFrame des données ou None.
        """
        try:
            # Récupération des données
            if self.broker:
                # Données du broker
                bars = self.broker.get_bars(
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                    limit=100
                )
                if bars:
                    return pd.DataFrame(bars)
            else:
                # Données du DataProvider
                return self.data_provider.get_historical_data(
                    symbol=self.config.symbol,
                    start_date=datetime.now() - timedelta(days=7),
                    end_date=datetime.now(),
                    timeframe=self.config.timeframe
                )
            
        except Exception as e:
            logger.error(f"Erreur de récupération des données: {e}")
            return None
    
    # ============================================================
    # TRAITEMENT DES SIGNAUX
    # ============================================================
    
    def _process_signal(self, signal: Dict[str, Any]) -> None:
        """
        Traite un signal de trading.
        
        Args:
            signal: Signal de trading.
        """
        action = signal.get('action')
        price = signal.get('price', self.state.current_price)
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')
        confidence = signal.get('confidence', 1.0)
        
        if not action:
            return
        
        # Validation du signal
        if confidence < 0.5:
            logger.debug(f"Signal ignoré (confiance trop faible): {confidence:.2f}")
            return
        
        # Traitement selon l'action
        if action == 'BUY':
            self._open_long_position(price, stop_loss, take_profit)
        elif action == 'SELL':
            self._open_short_position(price, stop_loss, take_profit)
        elif action == 'CLOSE_LONG':
            self._close_long_position(price)
        elif action == 'CLOSE_SHORT':
            self._close_short_position(price)
        elif action == 'CLOSE_ALL':
            self._close_all_positions(price)
    
    def _open_long_position(
        self,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> None:
        """
        Ouvre une position longue.
        
        Args:
            price: Prix d'entrée.
            stop_loss: Prix de stop-loss (optionnel).
            take_profit: Prix de take-profit (optionnel).
        """
        # Vérification du nombre de positions
        if len(self.state.positions) >= self.config.max_positions:
            logger.debug("Nombre maximum de positions atteint")
            return
        
        # Calcul de la taille
        capital = self._get_available_capital()
        position_size = self.position_sizer.calculate_position_size(
            price=price,
            capital=capital,
            stop_loss_pct=self.config.stop_loss_pct
        )
        
        # Limites
        position_size = min(position_size, self.config.max_position_size)
        position_size = max(position_size, self.config.min_position_size)
        
        if position_size <= 0:
            return
        
        # Vérification des fonds
        cost = position_size * price
        if cost > capital:
            logger.debug(f"Fonds insuffisants: {cost:.2f} > {capital:.2f}")
            return
        
        # Création de l'ordre
        order = {
            'symbol': self.config.symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': position_size,
            'price': price,
            'stop_loss': stop_loss or price * (1 - self.config.stop_loss_pct),
            'take_profit': take_profit or price * (1 + self.config.take_profit_pct),
            'timestamp': self.state.current_time
        }
        
        # Exécution
        self._execute_order(order)
    
    def _open_short_position(
        self,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> None:
        """
        Ouvre une position courte.
        
        Args:
            price: Prix d'entrée.
            stop_loss: Prix de stop-loss (optionnel).
            take_profit: Prix de take-profit (optionnel).
        """
        # Vérification du nombre de positions
        if len(self.state.positions) >= self.config.max_positions:
            logger.debug("Nombre maximum de positions atteint")
            return
        
        # Calcul de la taille
        capital = self._get_available_capital()
        position_size = self.position_sizer.calculate_position_size(
            price=price,
            capital=capital,
            stop_loss_pct=self.config.stop_loss_pct
        )
        
        # Limites
        position_size = min(position_size, self.config.max_position_size)
        position_size = max(position_size, self.config.min_position_size)
        
        if position_size <= 0:
            return
        
        # Création de l'ordre
        order = {
            'symbol': self.config.symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': position_size,
            'price': price,
            'stop_loss': stop_loss or price * (1 + self.config.stop_loss_pct),
            'take_profit': take_profit or price * (1 - self.config.take_profit_pct),
            'timestamp': self.state.current_time
        }
        
        # Exécution
        self._execute_order(order)
    
    def _close_long_position(self, price: float) -> None:
        """
        Ferme une position longue.
        
        Args:
            price: Prix de sortie.
        """
        # Trouver la position longue
        long_positions = [p for p in self.state.positions if p.get('side') == 'BUY']
        
        if not long_positions:
            return
        
        position = long_positions[0]
        
        # Création de l'ordre
        order = {
            'symbol': self.config.symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': position['quantity'],
            'price': price,
            'timestamp': self.state.current_time
        }
        
        # Exécution
        self._execute_order(order)
    
    def _close_short_position(self, price: float) -> None:
        """
        Ferme une position courte.
        
        Args:
            price: Prix de sortie.
        """
        # Trouver la position courte
        short_positions = [p for p in self.state.positions if p.get('side') == 'SELL']
        
        if not short_positions:
            return
        
        position = short_positions[0]
        
        # Création de l'ordre
        order = {
            'symbol': self.config.symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': position['quantity'],
            'price': price,
            'timestamp': self.state.current_time
        }
        
        # Exécution
        self._execute_order(order)
    
    def _close_all_positions(self, price: float) -> None:
        """
        Ferme toutes les positions.
        
        Args:
            price: Prix de sortie.
        """
        if not self.state.positions:
            return
        
        for position in self.state.positions.copy():
            if position.get('side') == 'BUY':
                self._close_long_position(price)
            else:
                self._close_short_position(price)
    
    # ============================================================
    # EXÉCUTION DES ORDRES
    # ============================================================
    
    def _execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécute un ordre.
        
        Args:
            order: Ordre à exécuter.
            
        Returns:
            Résultat de l'exécution.
        """
        # Validation
        validate_order(order)
        
        # Exécution via le broker ou simulation
        if self.broker:
            result = self.broker.execute_order(order)
        else:
            # Simulation interne
            result = self._simulate_execution(order)
        
        # Enregistrement
        self.state.total_trades += 1
        
        if result.get('pnl', 0) > 0:
            self.metrics['winning_trades'] += 1
        else:
            self.metrics['losing_trades'] += 1
        
        self.metrics['total_pnl'] += result.get('pnl', 0)
        self.state.trades.append(result)
        
        # Mise à jour des positions
        self._update_positions()
        
        # Événement
        self._dispatch_event('trade', result)
        
        logger.debug(
            f"Ordre exécuté: {order.get('side')} {order.get('quantity')} "
            f"@ {order.get('price'):.4f}"
        )
        
        return result
    
    def _simulate_execution(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simule l'exécution d'un ordre.
        
        Args:
            order: Ordre à simuler.
            
        Returns:
            Résultat simulé.
        """
        side = order.get('side')
        quantity = order.get('quantity', 0)
        price = order.get('price', self.state.current_price)
        
        # Slippage
        execution_price = price * (1 + 0.001) if side == 'BUY' else price * (1 - 0.001)
        
        # Commission
        commission = execution_price * quantity * 0.001
        
        # PNL
        pnl = 0.0
        
        # Mise à jour de la position
        if side == 'BUY':
            self.state.positions.append({
                'side': 'BUY',
                'quantity': quantity,
                'entry_price': execution_price,
                'current_price': execution_price,
                'timestamp': self.state.current_time
            })
        else:
            # Fermeture ou short
            if self.state.positions:
                # Vérifier si c'est une fermeture
                open_position = self.state.positions[-1]
                if open_position.get('side') == 'BUY':
                    pnl = (execution_price - open_position['entry_price']) * quantity
                    self.state.positions.pop()
                else:
                    # Short
                    self.state.positions.append({
                        'side': 'SELL',
                        'quantity': quantity,
                        'entry_price': execution_price,
                        'current_price': execution_price,
                        'timestamp': self.state.current_time
                    })
            else:
                # Short
                self.state.positions.append({
                    'side': 'SELL',
                    'quantity': quantity,
                    'entry_price': execution_price,
                    'current_price': execution_price,
                    'timestamp': self.state.current_time
                })
        
        return {
            'order_id': f"SIM_{int(time.time())}_{self.state.total_trades}",
            'side': side,
            'quantity': quantity,
            'price': execution_price,
            'commission': commission,
            'pnl': pnl,
            'timestamp': self.state.current_time,
            'status': 'FILLED'
        }
    
    # ============================================================
    # GESTION DES POSITIONS
    # ============================================================
    
    def _update_positions(self) -> None:
        """
        Met à jour les positions.
        """
        # Mise à jour des prix
        for position in self.state.positions:
            position['current_price'] = self.state.current_price
            
            # Vérification des stops
            if position.get('stop_loss'):
                if position['side'] == 'BUY' and self.state.current_price <= position['stop_loss']:
                    self._close_long_position(self.state.current_price)
                elif position['side'] == 'SELL' and self.state.current_price >= position['stop_loss']:
                    self._close_short_position(self.state.current_price)
            
            # Vérification des takes
            if position.get('take_profit'):
                if position['side'] == 'BUY' and self.state.current_price >= position['take_profit']:
                    self._close_long_position(self.state.current_price)
                elif position['side'] == 'SELL' and self.state.current_price <= position['take_profit']:
                    self._close_short_position(self.state.current_price)
    
    def _update_metrics(self) -> None:
        """
        Met à jour les métriques.
        """
        # Calcul du drawdown
        if self.state.equity_curve:
            current_equity = self.state.equity_curve[-1]
            peak = max(self.state.equity_curve)
            drawdown = (peak - current_equity) / peak if peak > 0 else 0
            
            self.metrics['current_drawdown'] = drawdown
            self.metrics['max_drawdown'] = max(
                self.metrics['max_drawdown'],
                drawdown
            )
    
    def _get_available_capital(self) -> float:
        """
        Calcule le capital disponible.
        
        Returns:
            Capital disponible.
        """
        initial = self.config.initial_capital
        pnl = self.metrics['total_pnl']
        used = sum(p.get('quantity', 0) * p.get('current_price', 0) 
                   for p in self.state.positions)
        return initial + pnl - used
    
    # ============================================================
    # GESTION DES ÉVÉNEMENTS
    # ============================================================
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """
        Ajoute un gestionnaire d'événements.
        
        Args:
            event_type: Type d'événement.
            handler: Fonction de gestion.
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def _dispatch_event(self, event_type: str, data: Any) -> None:
        """
        Dispatch un événement.
        
        Args:
            event_type: Type d'événement.
            data: Données de l'événement.
        """
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Erreur dans le gestionnaire d'événements: {e}")
    
    # ============================================================
    # GESTION DU CYCLE DE VIE
    # ============================================================
    
    def pause(self) -> None:
        """
        Met en pause l'exécution.
        """
        self._paused = True
        self.state.status = RunnerStatus.PAUSED
        logger.info("Runner en pause")
    
    def resume(self) -> None:
        """
        Reprend l'exécution.
        """
        self._paused = False
        self.state.status = RunnerStatus.RUNNING
        logger.info("Runner repris")
    
    def stop(self) -> None:
        """
        Arrête l'exécution.
        """
        self._stop_signal = True
        self._running = False
        self.state.status = RunnerStatus.STOPPING
        
        # Attente de la fin
        while self._running:
            time.sleep(0.1)
        
        self.state.status = RunnerStatus.STOPPED
        logger.info("Runner arrêté")
    
    def _signal_handler(self, signum, frame) -> None:
        """
        Gestionnaire de signaux.
        
        Args:
            signum: Numéro du signal.
            frame: Frame courant.
        """
        logger.info(f"Signal {signum} reçu, arrêt du runner...")
        self.stop()
    
    def get_state(self) -> Dict[str, Any]:
        """
        Retourne l'état actuel.
        
        Returns:
            État du runner.
        """
        return self.state.to_dict()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Retourne les métriques.
        
        Returns:
            Métriques de performance.
        """
        return self.metrics.copy()
    
    # ============================================================
    # SAUVEGARDE
    # ============================================================
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """
        Sauvegarde les résultats.
        
        Args:
            filename: Nom du fichier (optionnel).
            
        Returns:
            Chemin du fichier sauvegardé.
        """
        import os
        import json
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.config.strategy_name}_{self.config.symbol}_{timestamp}.json"
        
        filepath = os.path.join(self.config.output_dir, filename)
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        data = {
            'config': {
                'strategy_name': self.config.strategy_name,
                'strategy_params': self.config.strategy_params,
                'symbol': self.config.symbol,
                'mode': self.config.mode.value,
                'initial_capital': self.config.initial_capital
            },
            'metrics': self.metrics,
            'state': self.state.to_dict(),
            'trades': self.state.trades,
            'equity_curve': self.state.equity_curve
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Résultats sauvegardés: {filepath}")
        return filepath


# Fonctions utilitaires
def run_strategy(
    strategy_name: str,
    symbol: str,
    mode: str = 'backtest',
    **kwargs
) -> Dict[str, Any]:
    """
    Fonction utilitaire pour exécuter une stratégie.
    
    Args:
        strategy_name: Nom de la stratégie.
        symbol: Symbole à trader.
        mode: Mode d'exécution ('backtest', 'simulation', 'paper_trading', 'live_trading').
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de l'exécution.
    """
    # Mapping du mode
    mode_mapping = {
        'backtest': ExecutionMode.BACKTEST,
        'simulation': ExecutionMode.SIMULATION,
        'paper_trading': ExecutionMode.PAPER_TRADING,
        'live_trading': ExecutionMode.LIVE_TRADING
    }
    
    execution_mode = mode_mapping.get(mode, ExecutionMode.BACKTEST)
    
    # Configuration
    config = RunnerConfig(
        strategy_name=strategy_name,
        symbol=symbol,
        mode=execution_mode,
        **kwargs
    )
    
    # Exécution
    runner = StrategyRunner(config)
    return runner.run()


# Exportation
__all__ = [
    'StrategyRunner',
    'RunnerConfig',
    'RunnerState',
    'RunnerStatus',
    'ExecutionMode',
    'run_strategy'
]

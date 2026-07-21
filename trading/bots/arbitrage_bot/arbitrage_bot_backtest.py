"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Backtest
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Backtesting engine for the arbitrage bot
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Imports internes
from .core.arbitrage_engine import ArbitrageEngine
from .core.exchange_manager import ExchangeManager
from .core.strategy_manager import StrategyManager
from .core.risk_manager import RiskManager
from .core.execution_engine import ExecutionEngine
from .core.market_data import MarketData
from .core.notification_manager import NotificationManager
from .core.data_manager import DataManager
from .core.metrics_collector import MetricsCollector
from .config import ConfigLoader

from .utils import (
    StatisticsUtils,
    FinancialMathUtils,
    DateTimeUtils,
    NumberFormatter,
    TableFormatter,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# BACKTEST ENGINE
# ============================================================

class BacktestEngine:
    """
    Moteur de backtesting
    
    Permet de tester les stratégies sur des données historiques
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        data_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        initial_balance: float = 10000.0,
        commission: float = 0.001,
        slippage: float = 0.002
    ):
        """
        Initialise le moteur de backtest
        
        Args:
            config_path: Chemin de la configuration
            data_dir: Répertoire des données
            output_dir: Répertoire de sortie
            initial_balance: Solde initial
            commission: Commission
            slippage: Slippage
        """
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.data_dir = Path(data_dir) if data_dir else Path("data/historical")
        self.output_dir = Path(output_dir) if output_dir else Path("reports/backtest")
        self.initial_balance = initial_balance
        self.commission = commission
        self.slippage = slippage
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Données
        self.data = {}
        self.results = {}
        self.metrics = {}
        
        logger.info("BacktestEngine initialized")
    
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
            'data_manager': DataManager(),
            'metrics_collector': MetricsCollector(self.config),
            'risk_manager': RiskManager(self.config),
            'execution_engine': ExecutionEngine(self.config),
            'arbitrage_engine': ArbitrageEngine(self.config),
        }
        
        logger.info("Components initialized")
    
    # ============================================================
    # DATA LOADING
    # ============================================================
    
    def load_historical_data(
        self,
        start_date: str,
        end_date: str,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1m"
    ) -> Dict[str, pd.DataFrame]:
        """
        Charge les données historiques
        
        Args:
            start_date: Date de début
            end_date: Date de fin
            symbols: Symboles à charger
            timeframe: Timeframe
            
        Returns:
            Dict[str, pd.DataFrame]: Données chargées
        """
        logger.info(f"Loading historical data from {start_date} to {end_date}")
        
        if symbols is None:
            symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"]
        
        data = {}
        
        for symbol in symbols:
            # Charger les données
            symbol_data = self._load_symbol_data(symbol, start_date, end_date, timeframe)
            if not symbol_data.empty:
                data[symbol] = symbol_data
                logger.info(f"Loaded {len(symbol_data)} records for {symbol}")
        
        self.data = data
        return data
    
    def _load_symbol_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Charge les données d'un symbole
        
        Args:
            symbol: Symbole
            start_date: Date de début
            end_date: Date de fin
            timeframe: Timeframe
            
        Returns:
            pd.DataFrame: Données du symbole
        """
        # Générer des données simulées pour l'exemple
        # En production, charger depuis la base de données ou un fichier
        np.random.seed(42)
        
        dates = pd.date_range(start=start_date, end=end_date, freq=timeframe)
        n = len(dates)
        
        # Simuler des prix
        base_price = 50000.0 if "BTC" in symbol else 3000.0 if "ETH" in symbol else 150.0
        price = base_price
        
        prices = []
        volumes = []
        
        for i in range(n):
            # Mouvement brownien
            drift = 0.0001  # Tendance
            volatility = 0.002  # Volatilité
            
            change = np.random.normal(drift, volatility)
            price = price * (1 + change)
            
            prices.append(price)
            volumes.append(np.random.uniform(100, 1000))
        
        # Créer le DataFrame
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.005)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.005)) for p in prices],
            'close': prices,
            'volume': volumes,
        })
        
        return df
    
    # ============================================================
    # BACKTEST EXECUTION
    # ============================================================
    
    def run_backtest(
        self,
        strategy_type: str = "cross_exchange",
        strategy_params: Optional[Dict[str, Any]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1m"
    ) -> Dict[str, Any]:
        """
        Exécute un backtest
        
        Args:
            strategy_type: Type de stratégie
            strategy_params: Paramètres de la stratégie
            start_date: Date de début
            end_date: Date de fin
            symbols: Symboles à tester
            timeframe: Timeframe
            
        Returns:
            Dict[str, Any]: Résultats du backtest
        """
        logger.info(f"Running backtest for {strategy_type}")
        
        # Charger les données
        if not self.data or start_date:
            start_date = start_date or "2024-01-01"
            end_date = end_date or "2024-12-31"
            self.load_historical_data(start_date, end_date, symbols, timeframe)
        
        # Initialiser les résultats
        results = {
            'trades': [],
            'positions': [],
            'balances': [],
            'metrics': {},
        }
        
        balance = self.initial_balance
        positions = []
        
        # Simuler le trading
        for symbol, df in self.data.items():
            logger.info(f"Processing {symbol} with {len(df)} records")
            
            # Simuler les trades
            trades = self._simulate_trades(df, symbol, balance, strategy_type, strategy_params)
            
            # Mettre à jour les résultats
            results['trades'].extend(trades)
            
            # Mettre à jour le solde
            for trade in trades:
                balance += trade.get('pnl', 0)
                results['balances'].append({
                    'timestamp': trade['timestamp'],
                    'balance': balance,
                })
        
        # Calculer les métriques
        results['metrics'] = self._calculate_metrics(results['trades'], results['balances'])
        
        self.results = results
        return results
    
    def _simulate_trades(
        self,
        df: pd.DataFrame,
        symbol: str,
        initial_balance: float,
        strategy_type: str,
        strategy_params: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Simule des trades sur les données
        
        Args:
            df: Données
            symbol: Symbole
            initial_balance: Solde initial
            strategy_type: Type de stratégie
            strategy_params: Paramètres de la stratégie
            
        Returns:
            List[Dict[str, Any]]: Trades simulés
        """
        trades = []
        balance = initial_balance
        position = None
        position_size = 0
        
        strategy_params = strategy_params or {}
        
        # Paramètres par défaut
        min_profit = strategy_params.get('min_profit', 0.001)
        max_position = strategy_params.get('max_position', 0.1)  # 10% du solde
        
        # Simuler sur chaque bougie
        for i in range(len(df)):
            current_price = df.iloc[i]['close']
            timestamp = df.iloc[i]['timestamp']
            
            # Simuler un signal
            signal = self._generate_signal(df, i, strategy_type)
            
            if signal == 'BUY' and position is None:
                # Acheter
                size = min(balance * 0.1, balance * max_position)
                if size > 0:
                    position = {
                        'entry_price': current_price,
                        'size': size,
                        'entry_time': timestamp,
                    }
                    position_size = size / current_price
                    balance -= size * (1 + self.commission)
                    
                    trades.append({
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'side': 'BUY',
                        'price': current_price,
                        'size': size,
                        'quantity': position_size,
                        'balance': balance,
                        'pnl': 0,
                    })
            
            elif signal == 'SELL' and position is not None:
                # Vendre
                pnl = (current_price - position['entry_price']) * position_size
                balance += position['size'] + pnl - self.commission * position['size']
                
                trades.append({
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'side': 'SELL',
                    'price': current_price,
                    'size': position['size'],
                    'quantity': position_size,
                    'balance': balance,
                    'pnl': pnl,
                })
                
                position = None
                position_size = 0
        
        return trades
    
    def _generate_signal(self, df: pd.DataFrame, index: int, strategy_type: str) -> Optional[str]:
        """
        Génère un signal de trading
        
        Args:
            df: Données
            index: Index actuel
            strategy_type: Type de stratégie
            
        Returns:
            Optional[str]: Signal ('BUY', 'SELL', None)
        """
        if index < 50:
            return None
        
        # Calculer les indicateurs
        close = df['close'].values
        current_price = close[index]
        sma_20 = np.mean(close[index-20:index])
        sma_50 = np.mean(close[index-50:index])
        
        # Stratégie cross-exchange (simplifiée)
        if strategy_type == "cross_exchange":
            # Simuler un spread entre deux exchanges
            spread = np.random.uniform(0.001, 0.005)
            
            if spread > 0.003:
                return 'BUY'
            elif spread < 0.001:
                return 'SELL'
        
        # Stratégie triangulaire (simplifiée)
        elif strategy_type == "triangular":
            # Simuler un profit triangulaire
            profit = np.random.uniform(-0.005, 0.005)
            
            if profit > 0.003:
                return 'BUY'
            elif profit < -0.003:
                return 'SELL'
        
        # Stratégie statistique (simplifiée)
        elif strategy_type == "statistical":
            # Calculer le z-score
            z_score = (current_price - sma_20) / np.std(close[index-20:index])
            
            if z_score < -2.0:
                return 'BUY'
            elif z_score > 2.0:
                return 'SELL'
        
        # Stratégie de momentum (simplifiée)
        elif strategy_type == "momentum":
            if sma_20 > sma_50 * 1.01:
                return 'BUY'
            elif sma_20 < sma_50 * 0.99:
                return 'SELL'
        
        return None
    
    def _calculate_metrics(self, trades: List[Dict[str, Any]], balances: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule les métriques de performance
        
        Args:
            trades: Liste des trades
            balances: Liste des soldes
            
        Returns:
            Dict[str, Any]: Métriques
        """
        if not trades:
            return {}
        
        # Convertir en DataFrame
        trades_df = pd.DataFrame(trades)
        
        # Métriques de base
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        total_pnl = trades_df['pnl'].sum()
        avg_pnl = trades_df['pnl'].mean()
        max_pnl = trades_df['pnl'].max()
        min_pnl = trades_df['pnl'].min()
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        loss_rate = losing_trades / total_trades if total_trades > 0 else 0
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if losing_trades > 0 else 0
        
        profit_factor = (avg_win * winning_trades) / (avg_loss * losing_trades) if avg_loss > 0 and losing_trades > 0 else float('inf')
        
        # Rendements
        if balances:
            balances_df = pd.DataFrame(balances)
            initial_balance = balances_df.iloc[0]['balance']
            final_balance = balances_df.iloc[-1]['balance']
            total_return = (final_balance - initial_balance) / initial_balance if initial_balance > 0 else 0
            
            # Rendements journaliers
            balances_df['date'] = pd.to_datetime(balances_df['timestamp']).dt.date
            daily_returns = balances_df.groupby('date').last().pct_change().dropna()
            
            sharpe_ratio = FinancialMathUtils.sharpe_ratio(daily_returns.tolist(), 0.02)
            sortino_ratio = FinancialMathUtils.sortino_ratio(daily_returns.tolist(), 0.02)
            
            # Drawdown
            cum_pnl = balances_df['balance'].values
            running_max = np.maximum.accumulate(cum_pnl)
            drawdown = (running_max - cum_pnl) / running_max
            max_drawdown = drawdown.max() if len(drawdown) > 0 else 0
            avg_drawdown = drawdown.mean() if len(drawdown) > 0 else 0
            
            calmar_ratio = FinancialMathUtils.calmar_ratio(daily_returns.tolist(), max_drawdown) if max_drawdown > 0 else 0
        else:
            total_return = 0
            daily_returns = []
            sharpe_ratio = 0
            sortino_ratio = 0
            max_drawdown = 0
            avg_drawdown = 0
            calmar_ratio = 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_pnl': max_pnl,
            'min_pnl': min_pnl,
            'win_rate': win_rate,
            'loss_rate': loss_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown': max_drawdown,
            'avg_drawdown': avg_drawdown,
            'final_balance': balances[-1]['balance'] if balances else self.initial_balance,
        }
    
    # ============================================================
    # OPTIMIZATION
    # ============================================================
    
    def optimize_parameters(
        self,
        strategy_type: str,
        param_grid: Dict[str, List[Any]],
        metric: str = 'sharpe_ratio',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimise les paramètres d'une stratégie
        
        Args:
            strategy_type: Type de stratégie
            param_grid: Grille de paramètres
            metric: Métrique à optimiser
            **kwargs: Arguments supplémentaires
            
        Returns:
            Dict[str, Any]: Meilleurs paramètres
        """
        logger.info(f"Optimizing parameters for {strategy_type}")
        
        # Générer toutes les combinaisons
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))
        
        best_params = None
        best_score = float('-inf')
        results = []
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            
            # Exécuter le backtest
            result = self.run_backtest(
                strategy_type=strategy_type,
                strategy_params=params,
                **kwargs
            )
            
            score = result['metrics'].get(metric, 0)
            
            results.append({
                'params': params,
                'score': score,
                'result': result,
            })
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': results,
        }
    
    # ============================================================
    # VISUALIZATION
    # ============================================================
    
    def generate_visualizations(self, output_format: str = 'html') -> Dict[str, Path]:
        """
        Génère des visualisations du backtest
        
        Args:
            output_format: Format de sortie
            
        Returns:
            Dict[str, Path]: Chemins des fichiers générés
        """
        logger.info(f"Generating visualizations in {output_format} format...")
        
        if not self.results:
            logger.warning("No backtest results available")
            return {}
        
        files = {}
        
        # 1. Equity Curve
        files['equity'] = self._plot_equity_curve(output_format)
        
        # 2. Drawdown Chart
        files['drawdown'] = self._plot_drawdown(output_format)
        
        # 3. Trade Distribution
        files['distribution'] = self._plot_trade_distribution(output_format)
        
        # 4. Monthly Returns
        files['monthly'] = self._plot_monthly_returns(output_format)
        
        # 5. Dashboard
        files['dashboard'] = self._plot_dashboard(output_format)
        
        return files
    
    def _plot_equity_curve(self, output_format: str) -> Path:
        """Génère la courbe d'équité"""
        balances = self.results.get('balances', [])
        if not balances:
            return None
        
        balances_df = pd.DataFrame(balances)
        
        fig = go.Figure()
        
        # Courbe d'équité
        fig.add_trace(go.Scatter(
            x=balances_df['timestamp'],
            y=balances_df['balance'],
            mode='lines',
            name='Equity',
            line=dict(color='blue', width=2),
            fill='tozeroy',
            fillcolor='rgba(0,0,255,0.1)',
        ))
        
        # Ligne de base
        fig.add_trace(go.Scatter(
            x=balances_df['timestamp'],
            y=[self.initial_balance] * len(balances_df),
            mode='lines',
            name='Initial Balance',
            line=dict(color='gray', width=1, dash='dash'),
        ))
        
        fig.update_layout(
            title='Equity Curve',
            xaxis_title='Time',
            yaxis_title='Balance (USD)',
            template='plotly_dark',
            hovermode='x unified',
            height=500,
        )
        
        return self._save_figure(fig, 'equity_curve', output_format)
    
    def _plot_drawdown(self, output_format: str) -> Path:
        """Génère le graphique de drawdown"""
        balances = self.results.get('balances', [])
        if not balances:
            return None
        
        balances_df = pd.DataFrame(balances)
        cum_pnl = balances_df['balance'].values
        running_max = np.maximum.accumulate(cum_pnl)
        drawdown = (running_max - cum_pnl) / running_max * 100
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=balances_df['timestamp'],
            y=drawdown,
            mode='lines',
            name='Drawdown',
            line=dict(color='red', width=2),
            fill='tozeroy',
            fillcolor='rgba(255,0,0,0.2)',
        ))
        
        fig.update_layout(
            title='Drawdown',
            xaxis_title='Time',
            yaxis_title='Drawdown (%)',
            template='plotly_dark',
            hovermode='x unified',
            height=400,
        )
        
        return self._save_figure(fig, 'drawdown', output_format)
    
    def _plot_trade_distribution(self, output_format: str) -> Path:
        """Génère la distribution des trades"""
        trades = self.results.get('trades', [])
        if not trades:
            return None
        
        trades_df = pd.DataFrame(trades)
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('PNL Distribution', 'Win/Loss Distribution')
        )
        
        # PNL Distribution
        fig.add_trace(
            go.Histogram(
                x=trades_df['pnl'],
                nbinsx=30,
                marker_color='blue',
                name='PNL',
            ),
            row=1, col=1
        )
        
        # Win/Loss Distribution
        win_loss = trades_df['pnl'].apply(lambda x: 'Win' if x > 0 else 'Loss')
        win_loss_counts = win_loss.value_counts()
        
        fig.add_trace(
            go.Bar(
                x=win_loss_counts.index,
                y=win_loss_counts.values,
                marker_color=['green' if x == 'Win' else 'red' for x in win_loss_counts.index],
                name='Win/Loss',
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title='Trade Distribution',
            template='plotly_dark',
            height=400,
            showlegend=False,
        )
        
        return self._save_figure(fig, 'trade_distribution', output_format)
    
    def _plot_monthly_returns(self, output_format: str) -> Path:
        """Génère les rendements mensuels"""
        trades = self.results.get('trades', [])
        if not trades:
            return None
        
        trades_df = pd.DataFrame(trades)
        trades_df['date'] = pd.to_datetime(trades_df['timestamp']).dt.date
        trades_df['month'] = pd.to_datetime(trades_df['timestamp']).dt.to_period('M')
        
        monthly_pnl = trades_df.groupby('month')['pnl'].sum()
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=[str(m) for m in monthly_pnl.index],
            y=monthly_pnl.values,
            marker_color=['green' if v > 0 else 'red' for v in monthly_pnl.values],
            name='Monthly PNL',
        ))
        
        fig.update_layout(
            title='Monthly Returns',
            xaxis_title='Month',
            yaxis_title='PNL (USD)',
            template='plotly_dark',
            height=400,
            showlegend=False,
        )
        
        return self._save_figure(fig, 'monthly_returns', output_format)
    
    def _plot_dashboard(self, output_format: str) -> Path:
        """Génère le tableau de bord"""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Equity Curve',
                'Drawdown',
                'Monthly Returns',
                'Trade Distribution'
            ),
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}],
                [{"type": "bar"}, {"type": "bar"}],
            ]
        )
        
        # 1. Equity Curve
        balances = self.results.get('balances', [])
        if balances:
            balances_df = pd.DataFrame(balances)
            fig.add_trace(
                go.Scatter(
                    x=balances_df['timestamp'],
                    y=balances_df['balance'],
                    mode='lines',
                    name='Equity',
                    line=dict(color='blue'),
                ),
                row=1, col=1
            )
        
        # 2. Drawdown
        if balances:
            cum_pnl = balances_df['balance'].values
            running_max = np.maximum.accumulate(cum_pnl)
            drawdown = (running_max - cum_pnl) / running_max * 100
            fig.add_trace(
                go.Scatter(
                    x=balances_df['timestamp'],
                    y=drawdown,
                    mode='lines',
                    name='Drawdown',
                    line=dict(color='red'),
                    fill='tozeroy',
                ),
                row=1, col=2
            )
        
        # 3. Monthly Returns
        trades = self.results.get('trades', [])
        if trades:
            trades_df = pd.DataFrame(trades)
            trades_df['month'] = pd.to_datetime(trades_df['timestamp']).dt.to_period('M')
            monthly_pnl = trades_df.groupby('month')['pnl'].sum()
            fig.add_trace(
                go.Bar(
                    x=[str(m) for m in monthly_pnl.index],
                    y=monthly_pnl.values,
                    marker_color=['green' if v > 0 else 'red' for v in monthly_pnl.values],
                    name='Monthly PNL',
                ),
                row=2, col=1
            )
        
        # 4. Trade Distribution
        if trades:
            win_loss = trades_df['pnl'].apply(lambda x: 'Win' if x > 0 else 'Loss')
            win_loss_counts = win_loss.value_counts()
            fig.add_trace(
                go.Bar(
                    x=win_loss_counts.index,
                    y=win_loss_counts.values,
                    marker_color=['green' if x == 'Win' else 'red' for x in win_loss_counts.index],
                    name='Win/Loss',
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            title='Backtest Dashboard',
            template='plotly_dark',
            height=800,
            showlegend=False,
        )
        
        return self._save_figure(fig, 'backtest_dashboard', output_format)
    
    def _save_figure(self, fig: go.Figure, name: str, output_format: str) -> Path:
        """Sauvegarde une figure"""
        output_path = self.output_dir / f"{name}.{output_format}"
        
        if output_format == 'html':
            fig.write_html(str(output_path))
        elif output_format == 'png':
            fig.write_image(str(output_path), scale=2)
        else:
            fig.write_html(str(output_path))
        
        return output_path
    
    # ============================================================
    # REPORT GENERATION
    # ============================================================
    
    def generate_report(self, output_format: str = 'html') -> Path:
        """
        Génère un rapport de backtest
        
        Args:
            output_format: Format de sortie ('html', 'pdf', 'json')
            
        Returns:
            Path: Chemin du rapport généré
        """
        logger.info(f"Generating backtest report in {output_format} format...")
        
        if not self.results:
            logger.warning("No backtest results available")
            return None
        
        # Générer les visualisations
        self.generate_visualizations('html' if output_format == 'html' else 'png')
        
        # Créer le rapport
        if output_format == 'html':
            report_path = self._generate_html_report()
        elif output_format == 'json':
            report_path = self._generate_json_report()
        else:
            report_path = self._generate_html_report()
        
        logger.info(f"Report generated: {report_path}")
        return report_path
    
    def _generate_html_report(self) -> Path:
        """Génère un rapport HTML"""
        metrics = self.results.get('metrics', {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>NEXUS Arbitrage Bot Backtest Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #1a1a2e; color: #e0e0e0; }}
                h1 {{ color: #00d4aa; border-bottom: 2px solid #00d4aa; padding-bottom: 10px; }}
                h2 {{ color: #00d4aa; margin-top: 30px; }}
                .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .card {{ background: #16213e; padding: 20px; border-radius: 10px; border: 1px solid #0f3460; }}
                .card .value {{ font-size: 24px; font-weight: bold; color: #00d4aa; }}
                .card .label {{ font-size: 14px; color: #a0a0a0; }}
                .chart {{ margin: 30px 0; border: 1px solid #0f3460; border-radius: 10px; overflow: hidden; }}
                .chart iframe {{ width: 100%; height: 500px; border: none; }}
                .metrics {{ background: #16213e; padding: 20px; border-radius: 10px; border: 1px solid #0f3460; margin: 20px 0; }}
                .metrics table {{ width: 100%; border-collapse: collapse; }}
                .metrics td {{ padding: 10px; border-bottom: 1px solid #0f3460; }}
                .metrics .label {{ color: #a0a0a0; }}
                .metrics .value {{ color: #00d4aa; font-weight: bold; }}
                .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #0f3460; text-align: center; color: #a0a0a0; }}
            </style>
        </head>
        <body>
            <h1>🚀 NEXUS Arbitrage Bot Backtest Report</h1>
            <p>Generated: {datetime.now().isoformat()}</p>
            
            <h2>📊 Performance Summary</h2>
            <div class="summary">
                <div class="card">
                    <div class="value">{metrics.get('total_trades', 0)}</div>
                    <div class="label">Total Trades</div>
                </div>
                <div class="card">
                    <div class="value">${metrics.get('total_pnl', 0):.2f}</div>
                    <div class="label">Total PNL</div>
                </div>
                <div class="card">
                    <div class="value">{metrics.get('win_rate', 0)*100:.1f}%</div>
                    <div class="label">Win Rate</div>
                </div>
                <div class="card">
                    <div class="value">{metrics.get('sharpe_ratio', 0):.2f}</div>
                    <div class="label">Sharpe Ratio</div>
                </div>
                <div class="card">
                    <div class="value">{metrics.get('max_drawdown', 0)*100:.1f}%</div>
                    <div class="label">Max Drawdown</div>
                </div>
                <div class="card">
                    <div class="value">${metrics.get('final_balance', 0):.2f}</div>
                    <div class="label">Final Balance</div>
                </div>
            </div>
            
            <h2>📈 Detailed Metrics</h2>
            <div class="metrics">
                <table>
                    <tr>
                        <td class="label">Total Trades</td>
                        <td class="value">{metrics.get('total_trades', 0)}</td>
                        <td class="label">Winning Trades</td>
                        <td class="value">{metrics.get('winning_trades', 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Losing Trades</td>
                        <td class="value">{metrics.get('losing_trades', 0)}</td>
                        <td class="label">Win Rate</td>
                        <td class="value">{metrics.get('win_rate', 0)*100:.1f}%</td>
                    </tr>
                    <tr>
                        <td class="label">Total PNL</td>
                        <td class="value">${metrics.get('total_pnl', 0):.2f}</td>
                        <td class="label">Avg PNL</td>
                        <td class="value">${metrics.get('avg_pnl', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">Max PNL</td>
                        <td class="value">${metrics.get('max_pnl', 0):.2f}</td>
                        <td class="label">Min PNL</td>
                        <td class="value">${metrics.get('min_pnl', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">Avg Win</td>
                        <td class="value">${metrics.get('avg_win', 0):.2f}</td>
                        <td class="label">Avg Loss</td>
                        <td class="value">${metrics.get('avg_loss', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">Profit Factor</td>
                        <td class="value">{metrics.get('profit_factor', 0):.2f}</td>
                        <td class="label">Total Return</td>
                        <td class="value">{metrics.get('total_return', 0)*100:.1f}%</td>
                    </tr>
                    <tr>
                        <td class="label">Sharpe Ratio</td>
                        <td class="value">{metrics.get('sharpe_ratio', 0):.2f}</td>
                        <td class="label">Sortino Ratio</td>
                        <td class="value">{metrics.get('sortino_ratio', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">Calmar Ratio</td>
                        <td class="value">{metrics.get('calmar_ratio', 0):.2f}</td>
                        <td class="label">Max Drawdown</td>
                        <td class="value">{metrics.get('max_drawdown', 0)*100:.1f}%</td>
                    </tr>
                    <tr>
                        <td class="label">Avg Drawdown</td>
                        <td class="value">{metrics.get('avg_drawdown', 0)*100:.1f}%</td>
                        <td class="label">Final Balance</td>
                        <td class="value">${metrics.get('final_balance', 0):.2f}</td>
                    </tr>
                </table>
            </div>
            
            <h2>📈 Charts</h2>
            <div class="chart">
                <iframe src="equity_curve.html"></iframe>
            </div>
            <div class="chart">
                <iframe src="drawdown.html"></iframe>
            </div>
            <div class="chart">
                <iframe src="monthly_returns.html"></iframe>
            </div>
            <div class="chart">
                <iframe src="trade_distribution.html"></iframe>
            </div>
            
            <div class="footer">
                <p>NEXUS Arbitrage Bot v2.0.0 | Copyright © 2026 NEXUS QUANTUM LTD</p>
            </div>
        </body>
        </html>
        """
        
        report_path = self.output_dir / "backtest_report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return report_path
    
    def _generate_json_report(self) -> Path:
        """Génère un rapport JSON"""
        report = {
            'metadata': {
                'version': '2.0.0',
                'timestamp': datetime.now().isoformat(),
                'initial_balance': self.initial_balance,
            },
            'metrics': self.results.get('metrics', {}),
            'trades_count': len(self.results.get('trades', [])),
            'summary': {
                'total_trades': len(self.results.get('trades', [])),
                'total_pnl': self.results.get('metrics', {}).get('total_pnl', 0),
                'win_rate': self.results.get('metrics', {}).get('win_rate', 0),
                'sharpe_ratio': self.results.get('metrics', {}).get('sharpe_ratio', 0),
                'max_drawdown': self.results.get('metrics', {}).get('max_drawdown', 0),
            }
        }
        
        report_path = self.output_dir / "backtest_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        return report_path
    
    # ============================================================
    # DATA EXPORT
    # ============================================================
    
    def export_results(self, format: str = 'csv') -> Dict[str, Path]:
        """
        Exporte les résultats du backtest
        
        Args:
            format: Format de sortie ('csv', 'json', 'parquet')
            
        Returns:
            Dict[str, Path]: Chemins des fichiers exportés
        """
        logger.info(f"Exporting results in {format} format...")
        
        files = {}
        export_dir = self.output_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        # Exporter les trades
        if self.results.get('trades'):
            trades_df = pd.DataFrame(self.results['trades'])
            file_path = export_dir / f"trades.{format}"
            
            if format == 'csv':
                trades_df.to_csv(file_path, index=False)
            elif format == 'json':
                trades_df.to_json(file_path, orient='records', indent=2)
            else:
                trades_df.to_csv(file_path, index=False)
            
            files['trades'] = file_path
        
        # Exporter les balances
        if self.results.get('balances'):
            balances_df = pd.DataFrame(self.results['balances'])
            file_path = export_dir / f"balances.{format}"
            
            if format == 'csv':
                balances_df.to_csv(file_path, index=False)
            elif format == 'json':
                balances_df.to_json(file_path, orient='records', indent=2)
            else:
                balances_df.to_csv(file_path, index=False)
            
            files['balances'] = file_path
        
        # Exporter les métriques
        if self.results.get('metrics'):
            file_path = export_dir / f"metrics.{format}"
            
            if format == 'json':
                with open(file_path, 'w') as f:
                    json.dump(self.results['metrics'], f, indent=2)
            else:
                # CSV pour les métriques
                metrics_df = pd.DataFrame([self.results['metrics']])
                metrics_df.to_csv(file_path, index=False)
            
            files['metrics'] = file_path
        
        return files

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Backtest")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-s", "--start",
        help="Start date (YYYY-MM-DD)",
        default="2024-01-01"
    )
    parser.add_argument(
        "-e", "--end",
        help="End date (YYYY-MM-DD)",
        default="2024-12-31"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory",
        default="reports/backtest"
    )
    parser.add_argument(
        "-f", "--format",
        help="Output format (html, pdf, json)",
        default="html"
    )
    parser.add_argument(
        "-S", "--strategy",
        help="Strategy type",
        choices=["cross_exchange", "triangular", "statistical", "momentum"],
        default="cross_exchange"
    )
    parser.add_argument(
        "-b", "--balance",
        help="Initial balance",
        type=float,
        default=10000.0
    )
    parser.add_argument(
        "--no-viz",
        help="Skip visualizations",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Créer le moteur de backtest
    engine = BacktestEngine(
        config_path=args.config,
        output_dir=args.output,
        initial_balance=args.balance
    )
    
    # Exécuter le backtest
    results = engine.run_backtest(
        strategy_type=args.strategy,
        start_date=args.start,
        end_date=args.end
    )
    
    # Afficher les métriques
    metrics = results.get('metrics', {})
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades:        {metrics.get('total_trades', 0)}")
    print(f"Win Rate:            {metrics.get('win_rate', 0)*100:.1f}%")
    print(f"Total PNL:           ${metrics.get('total_pnl', 0):.2f}")
    print(f"Sharpe Ratio:        {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"Max Drawdown:        {metrics.get('max_drawdown', 0)*100:.1f}%")
    print(f"Final Balance:       ${metrics.get('final_balance', 0):.2f}")
    print("=" * 60)
    
    # Générer les visualisations
    if not args.no_viz:
        engine.generate_visualizations()
    
    # Générer le rapport
    report_path = engine.generate_report(args.format)
    print(f"\nReport generated: {report_path}")

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'BacktestEngine',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

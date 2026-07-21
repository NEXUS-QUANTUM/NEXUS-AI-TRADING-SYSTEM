"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Analyseur de performance et de données pour le bot d'arbitrage
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
import plotly.express as px
from plotly.subplots import make_subplots

# Imports internes
from .core.arbitrage_engine import ArbitrageEngine
from .core.exchange_manager import ExchangeManager
from .core.strategy_manager import StrategyManager
from .core.risk_manager import RiskManager
from .core.execution_engine import ExecutionEngine
from .core.market_data import MarketData
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
# ANALYZER
# ============================================================

class ArbitrageBotAnalyzer:
    """
    Analyseur du bot d'arbitrage
    
    Analyse les performances, les données et génère des rapports
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        data_dir: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        """
        Initialise l'analyseur
        
        Args:
            config_path: Chemin de la configuration
            data_dir: Répertoire des données
            output_dir: Répertoire de sortie
        """
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.data_dir = Path(data_dir) if data_dir else Path("data")
        self.output_dir = Path(output_dir) if output_dir else Path("reports")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Données
        self.data = {}
        self.performance = {}
        
        logger.info("ArbitrageBotAnalyzer initialized")
    
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
        }
        
        logger.info("Components initialized")
    
    # ============================================================
    # DATA LOADING
    # ============================================================
    
    def load_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Charge les données
        
        Args:
            start_date: Date de début
            end_date: Date de fin
            
        Returns:
            Dict[str, Any]: Données chargées
        """
        logger.info(f"Loading data from {start_date} to {end_date}")
        
        data = {}
        
        # Charger les trades
        data['trades'] = self._load_trades(start_date, end_date)
        
        # Charger les positions
        data['positions'] = self._load_positions(start_date, end_date)
        
        # Charger les opportunités
        data['opportunities'] = self._load_opportunities(start_date, end_date)
        
        # Charger les métriques
        data['metrics'] = self._load_metrics(start_date, end_date)
        
        # Charger les ordres
        data['orders'] = self._load_orders(start_date, end_date)
        
        # Charger les alertes
        data['alerts'] = self._load_alerts(start_date, end_date)
        
        self.data = data
        logger.info(f"Loaded {len(data['trades'])} trades, {len(data['positions'])} positions")
        
        return data
    
    def _load_trades(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Charge les trades"""
        # Simulation de chargement de données
        # En production, charger depuis la base de données
        
        # Générer des données simulées pour l'exemple
        np.random.seed(42)
        n = 1000
        
        dates = pd.date_range(
            start=start_date or "2024-01-01",
            end=end_date or "2024-12-31",
            periods=n
        )
        
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT']
        sides = ['BUY', 'SELL']
        statuses = ['FILLED', 'PARTIALLY_FILLED']
        
        trades = pd.DataFrame({
            'timestamp': dates,
            'symbol': np.random.choice(symbols, n),
            'side': np.random.choice(sides, n),
            'quantity': np.random.uniform(0.01, 10, n),
            'price': np.random.uniform(1000, 50000, n),
            'pnl': np.random.normal(0, 100, n),
            'fee': np.random.uniform(0.1, 10, n),
            'status': np.random.choice(statuses, n, p=[0.9, 0.1]),
            'exchange': np.random.choice(['Binance', 'Bybit', 'Coinbase'], n),
            'strategy': np.random.choice(['CrossExchange', 'Triangular', 'Statistical'], n),
        })
        
        return trades
    
    def _load_positions(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Charge les positions"""
        n = 500
        
        dates = pd.date_range(
            start=start_date or "2024-01-01",
            end=end_date or "2024-12-31",
            periods=n
        )
        
        positions = pd.DataFrame({
            'timestamp': dates,
            'symbol': np.random.choice(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'], n),
            'side': np.random.choice(['BUY', 'SELL'], n),
            'entry_price': np.random.uniform(1000, 50000, n),
            'current_price': np.random.uniform(1000, 50000, n),
            'quantity': np.random.uniform(0.01, 10, n),
            'pnl': np.random.normal(0, 100, n),
            'pnl_percent': np.random.normal(0, 0.02, n),
            'duration': np.random.uniform(60, 3600, n),
        })
        
        return positions
    
    def _load_opportunities(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Charge les opportunités"""
        n = 5000
        
        dates = pd.date_range(
            start=start_date or "2024-01-01",
            end=end_date or "2024-12-31",
            periods=n
        )
        
        opportunities = pd.DataFrame({
            'timestamp': dates,
            'symbol': np.random.choice(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT'], n),
            'spread': np.random.uniform(0.01, 1, n),
            'profit_percent': np.random.uniform(0.001, 0.02, n),
            'profit': np.random.uniform(1, 100, n),
            'exchange_a': np.random.choice(['Binance', 'Bybit', 'Coinbase'], n),
            'exchange_b': np.random.choice(['Binance', 'Bybit', 'Coinbase'], n),
            'volume': np.random.uniform(100, 10000, n),
            'executed': np.random.choice([True, False], n, p=[0.3, 0.7]),
        })
        
        return opportunities
    
    def _load_metrics(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Charge les métriques"""
        n = 1000
        
        dates = pd.date_range(
            start=start_date or "2024-01-01",
            end=end_date or "2024-12-31",
            periods=n
        )
        
        metrics = pd.DataFrame({
            'timestamp': dates,
            'sharpe_ratio': np.random.normal(1.5, 0.5, n),
            'sortino_ratio': np.random.normal(1.2, 0.4, n),
            'calmar_ratio': np.random.normal(1.0, 0.3, n),
            'win_rate': np.random.uniform(0.4, 0.7, n),
            'profit_factor': np.random.uniform(1.0, 2.0, n),
            'max_drawdown': np.random.uniform(0.05, 0.20, n),
            'avg_trade_duration': np.random.uniform(60, 600, n),
            'avg_win': np.random.uniform(50, 200, n),
            'avg_loss': np.random.uniform(30, 100, n),
        })
        
        return metrics
    
    def _load_orders(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Charge les ordres"""
        n = 2000
        
        dates = pd.date_range(
            start=start_date or "2024-01-01",
            end=end_date or "2024-12-31",
            periods=n
        )
        
        orders = pd.DataFrame({
            'timestamp': dates,
            'symbol': np.random.choice(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT'], n),
            'side': np.random.choice(['BUY', 'SELL'], n),
            'type': np.random.choice(['LIMIT', 'MARKET', 'STOP'], n, p=[0.6, 0.3, 0.1]),
            'quantity': np.random.uniform(0.01, 10, n),
            'price': np.random.uniform(1000, 50000, n),
            'executed': np.random.choice([True, False], n, p=[0.7, 0.3]),
            'status': np.random.choice(['FILLED', 'PARTIALLY_FILLED', 'CANCELED'], n, p=[0.7, 0.15, 0.15]),
        })
        
        return orders
    
    def _load_alerts(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Charge les alertes"""
        n = 500
        
        dates = pd.date_range(
            start=start_date or "2024-01-01",
            end=end_date or "2024-12-31",
            periods=n
        )
        
        alerts = pd.DataFrame({
            'timestamp': dates,
            'type': np.random.choice(['OPPORTUNITY', 'RISK', 'ERROR', 'SYSTEM'], n),
            'severity': np.random.choice(['INFO', 'WARNING', 'CRITICAL'], n, p=[0.6, 0.3, 0.1]),
            'message': np.random.choice([
                'New opportunity detected',
                'Risk threshold exceeded',
                'Connection lost',
                'Trade executed',
            ], n),
            'source': np.random.choice(['arbitrage_engine', 'risk_manager', 'exchange_manager'], n),
            'resolved': np.random.choice([True, False], n, p=[0.7, 0.3]),
        })
        
        return alerts
    
    # ============================================================
    # PERFORMANCE ANALYSIS
    # ============================================================
    
    def analyze_performance(self) -> Dict[str, Any]:
        """
        Analyse les performances
        
        Returns:
            Dict[str, Any]: Résultats de l'analyse
        """
        logger.info("Analyzing performance...")
        
        trades = self.data.get('trades', pd.DataFrame())
        positions = self.data.get('positions', pd.DataFrame())
        metrics = self.data.get('metrics', pd.DataFrame())
        
        if trades.empty:
            logger.warning("No trades data available")
            return {}
        
        # Performance de base
        performance = {
            'summary': self._analyze_summary(trades, positions),
            'pnl': self._analyze_pnl(trades),
            'win_rate': self._analyze_win_rate(trades),
            'risk': self._analyze_risk(trades, positions),
            'efficiency': self._analyze_efficiency(trades),
            'strategy': self._analyze_strategy_performance(trades),
            'symbol': self._analyze_symbol_performance(trades),
            'exchange': self._analyze_exchange_performance(trades),
            'metrics': self._analyze_metrics(metrics),
        }
        
        self.performance = performance
        return performance
    
    def _analyze_summary(self, trades: pd.DataFrame, positions: pd.DataFrame) -> Dict[str, Any]:
        """Analyse le résumé"""
        return {
            'total_trades': len(trades),
            'total_positions': len(positions),
            'total_pnl': trades['pnl'].sum(),
            'avg_pnl': trades['pnl'].mean(),
            'max_pnl': trades['pnl'].max(),
            'min_pnl': trades['pnl'].min(),
            'total_fees': trades['fee'].sum(),
            'avg_fee': trades['fee'].mean(),
            'total_duration': positions['duration'].sum() if not positions.empty else 0,
            'avg_duration': positions['duration'].mean() if not positions.empty else 0,
        }
    
    def _analyze_pnl(self, trades: pd.DataFrame) -> Dict[str, Any]:
        """Analyse le P&L"""
        pnl = trades['pnl']
        
        return {
            'total': pnl.sum(),
            'mean': pnl.mean(),
            'median': pnl.median(),
            'std': pnl.std(),
            'max': pnl.max(),
            'min': pnl.min(),
            'positive': pnl[pnl > 0].sum(),
            'negative': pnl[pnl < 0].sum(),
            'positive_count': len(pnl[pnl > 0]),
            'negative_count': len(pnl[pnl < 0]),
            'cumulative': pnl.cumsum().tolist(),
        }
    
    def _analyze_win_rate(self, trades: pd.DataFrame) -> Dict[str, Any]:
        """Analyse le taux de victoire"""
        total = len(trades)
        wins = len(trades[trades['pnl'] > 0])
        losses = len(trades[trades['pnl'] < 0])
        
        win_rate = wins / total if total > 0 else 0
        loss_rate = losses / total if total > 0 else 0
        
        avg_win = trades[trades['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
        avg_loss = abs(trades[trades['pnl'] < 0]['pnl'].mean()) if losses > 0 else 0
        
        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'loss_rate': loss_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_loss_ratio': avg_win / avg_loss if avg_loss > 0 else float('inf'),
            'profit_factor': (avg_win * wins) / (avg_loss * losses) if avg_loss > 0 and losses > 0 else float('inf'),
        }
    
    def _analyze_risk(self, trades: pd.DataFrame, positions: pd.DataFrame) -> Dict[str, Any]:
        """Analyse le risque"""
        pnl = trades['pnl'].values
        
        # Drawdown
        cum_pnl = np.cumsum(pnl)
        running_max = np.maximum.accumulate(cum_pnl)
        drawdown = (running_max - cum_pnl) / running_max if running_max.max() > 0 else 0
        
        max_drawdown = drawdown.max() if len(drawdown) > 0 else 0
        avg_drawdown = drawdown.mean() if len(drawdown) > 0 else 0
        
        # Sharpe Ratio
        returns = pnl / (pnl.sum() if pnl.sum() != 0 else 1)
        sharpe = FinancialMathUtils.sharpe_ratio(returns.tolist(), 0.02) if len(returns) > 0 else 0
        
        # Sortino Ratio
        sortino = FinancialMathUtils.sortino_ratio(returns.tolist(), 0.02) if len(returns) > 0 else 0
        
        # Calmar Ratio
        calmar = FinancialMathUtils.calmar_ratio(returns.tolist(), max_drawdown) if max_drawdown > 0 else 0
        
        return {
            'max_drawdown': max_drawdown,
            'avg_drawdown': avg_drawdown,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'var_95': np.percentile(pnl, 5) if len(pnl) > 0 else 0,
            'cvar_95': pnl[pnl < np.percentile(pnl, 5)].mean() if len(pnl) > 0 else 0,
        }
    
    def _analyze_efficiency(self, trades: pd.DataFrame) -> Dict[str, Any]:
        """Analyse l'efficacité"""
        if trades.empty:
            return {}
        
        # Temps entre les trades
        timestamps = trades['timestamp'].sort_values()
        if len(timestamps) > 1:
            time_between = timestamps.diff().dt.total_seconds().dropna()
            avg_time_between = time_between.mean()
            max_time_between = time_between.max()
            min_time_between = time_between.min()
        else:
            avg_time_between = 0
            max_time_between = 0
            min_time_between = 0
        
        return {
            'avg_time_between_trades': avg_time_between,
            'max_time_between_trades': max_time_between,
            'min_time_between_trades': min_time_between,
            'trades_per_minute': len(trades) / (trades['timestamp'].max() - trades['timestamp'].min()).total_seconds() * 60 if len(trades) > 1 else 0,
            'efficiency_ratio': len(trades) / (len(trades) + len(trades[trades['status'] == 'PARTIALLY_FILLED'])) if len(trades) > 0 else 0,
        }
    
    def _analyze_strategy_performance(self, trades: pd.DataFrame) -> Dict[str, Any]:
        """Analyse la performance par stratégie"""
        if trades.empty:
            return {}
        
        strategies = trades['strategy'].unique()
        result = {}
        
        for strategy in strategies:
            strategy_trades = trades[trades['strategy'] == strategy]
            result[strategy] = {
                'total_trades': len(strategy_trades),
                'total_pnl': strategy_trades['pnl'].sum(),
                'avg_pnl': strategy_trades['pnl'].mean(),
                'win_rate': len(strategy_trades[strategy_trades['pnl'] > 0]) / len(strategy_trades) if len(strategy_trades) > 0 else 0,
            }
        
        return result
    
    def _analyze_symbol_performance(self, trades: pd.DataFrame) -> Dict[str, Any]:
        """Analyse la performance par symbole"""
        if trades.empty:
            return {}
        
        symbols = trades['symbol'].unique()
        result = {}
        
        for symbol in symbols:
            symbol_trades = trades[trades['symbol'] == symbol]
            result[symbol] = {
                'total_trades': len(symbol_trades),
                'total_pnl': symbol_trades['pnl'].sum(),
                'avg_pnl': symbol_trades['pnl'].mean(),
                'win_rate': len(symbol_trades[symbol_trades['pnl'] > 0]) / len(symbol_trades) if len(symbol_trades) > 0 else 0,
            }
        
        return result
    
    def _analyze_exchange_performance(self, trades: pd.DataFrame) -> Dict[str, Any]:
        """Analyse la performance par exchange"""
        if trades.empty:
            return {}
        
        exchanges = trades['exchange'].unique()
        result = {}
        
        for exchange in exchanges:
            exchange_trades = trades[trades['exchange'] == exchange]
            result[exchange] = {
                'total_trades': len(exchange_trades),
                'total_pnl': exchange_trades['pnl'].sum(),
                'avg_pnl': exchange_trades['pnl'].mean(),
                'win_rate': len(exchange_trades[exchange_trades['pnl'] > 0]) / len(exchange_trades) if len(exchange_trades) > 0 else 0,
            }
        
        return result
    
    def _analyze_metrics(self, metrics: pd.DataFrame) -> Dict[str, Any]:
        """Analyse les métriques"""
        if metrics.empty:
            return {}
        
        return {
            'sharpe_ratio': metrics['sharpe_ratio'].mean(),
            'sortino_ratio': metrics['sortino_ratio'].mean(),
            'calmar_ratio': metrics['calmar_ratio'].mean(),
            'win_rate': metrics['win_rate'].mean(),
            'profit_factor': metrics['profit_factor'].mean(),
            'max_drawdown': metrics['max_drawdown'].mean(),
            'avg_trade_duration': metrics['avg_trade_duration'].mean(),
            'avg_win': metrics['avg_win'].mean(),
            'avg_loss': metrics['avg_loss'].mean(),
        }
    
    # ============================================================
    # OPPORTUNITY ANALYSIS
    # ============================================================
    
    def analyze_opportunities(self) -> Dict[str, Any]:
        """
        Analyse les opportunités
        
        Returns:
            Dict[str, Any]: Résultats de l'analyse
        """
        logger.info("Analyzing opportunities...")
        
        opportunities = self.data.get('opportunities', pd.DataFrame())
        
        if opportunities.empty:
            logger.warning("No opportunities data available")
            return {}
        
        return {
            'summary': self._analyze_opportunity_summary(opportunities),
            'patterns': self._analyze_opportunity_patterns(opportunities),
            'efficiency': self._analyze_opportunity_efficiency(opportunities),
        }
    
    def _analyze_opportunity_summary(self, opportunities: pd.DataFrame) -> Dict[str, Any]:
        """Analyse le résumé des opportunités"""
        return {
            'total': len(opportunities),
            'executed': len(opportunities[opportunities['executed'] == True]),
            'execution_rate': len(opportunities[opportunities['executed'] == True]) / len(opportunities) if len(opportunities) > 0 else 0,
            'avg_spread': opportunities['spread'].mean(),
            'avg_profit': opportunities['profit'].mean(),
            'total_profit': opportunities['profit'].sum(),
            'max_profit': opportunities['profit'].max(),
            'min_profit': opportunities['profit'].min(),
            'avg_profit_percent': opportunities['profit_percent'].mean(),
            'max_profit_percent': opportunities['profit_percent'].max(),
            'min_profit_percent': opportunities['profit_percent'].min(),
        }
    
    def _analyze_opportunity_patterns(self, opportunities: pd.DataFrame) -> Dict[str, Any]:
        """Analyse les motifs des opportunités"""
        if opportunities.empty:
            return {}
        
        # Par symbole
        symbol_analysis = {}
        for symbol in opportunities['symbol'].unique():
            symbol_opps = opportunities[opportunities['symbol'] == symbol]
            symbol_analysis[symbol] = {
                'count': len(symbol_opps),
                'avg_spread': symbol_opps['spread'].mean(),
                'avg_profit': symbol_opps['profit'].mean(),
                'execution_rate': len(symbol_opps[symbol_opps['executed'] == True]) / len(symbol_opps) if len(symbol_opps) > 0 else 0,
            }
        
        # Par exchange
        exchange_analysis = {}
        for exchange in opportunities['exchange_a'].unique():
            exchange_opps = opportunities[opportunities['exchange_a'] == exchange]
            exchange_analysis[exchange] = {
                'count': len(exchange_opps),
                'avg_spread': exchange_opps['spread'].mean(),
                'execution_rate': len(exchange_opps[exchange_opps['executed'] == True]) / len(exchange_opps) if len(exchange_opps) > 0 else 0,
            }
        
        return {
            'by_symbol': symbol_analysis,
            'by_exchange': exchange_analysis,
        }
    
    def _analyze_opportunity_efficiency(self, opportunities: pd.DataFrame) -> Dict[str, Any]:
        """Analyse l'efficacité des opportunités"""
        if opportunities.empty:
            return {}
        
        executed = opportunities[opportunities['executed'] == True]
        
        return {
            'execution_rate': len(executed) / len(opportunities) if len(opportunities) > 0 else 0,
            'avg_time_to_execute': (executed['timestamp'].max() - executed['timestamp'].min()).total_seconds() / len(executed) if len(executed) > 0 else 0,
            'profit_ratio': executed['profit'].sum() / opportunities['profit'].sum() if opportunities['profit'].sum() > 0 else 0,
            'spread_capture': executed['spread'].mean() / opportunities['spread'].mean() if opportunities['spread'].mean() > 0 else 0,
        }
    
    # ============================================================
    # VISUALIZATION
    # ============================================================
    
    def generate_visualizations(self, output_format: str = 'html') -> Dict[str, Path]:
        """
        Génère des visualisations
        
        Args:
            output_format: Format de sortie ('html', 'png', 'pdf')
            
        Returns:
            Dict[str, Path]: Chemins des fichiers générés
        """
        logger.info(f"Generating visualizations in {output_format} format...")
        
        if not self.performance:
            self.analyze_performance()
        
        files = {}
        
        # 1. P&L Evolution
        files['pnl'] = self._plot_pnl_evolution(output_format)
        
        # 2. Win Rate Distribution
        files['win_rate'] = self._plot_win_rate_distribution(output_format)
        
        # 3. Performance by Strategy
        files['strategy'] = self._plot_strategy_performance(output_format)
        
        # 4. Performance by Symbol
        files['symbol'] = self._plot_symbol_performance(output_format)
        
        # 5. Risk Metrics
        files['risk'] = self._plot_risk_metrics(output_format)
        
        # 6. Cumulative P&L
        files['cumulative'] = self._plot_cumulative_pnl(output_format)
        
        # 7. Opportunity Analysis
        files['opportunity'] = self._plot_opportunity_analysis(output_format)
        
        # 8. Dashboard
        files['dashboard'] = self._plot_dashboard(output_format)
        
        logger.info(f"Generated {len(files)} visualizations")
        
        return files
    
    def _plot_pnl_evolution(self, output_format: str) -> Path:
        """Génère le graphique d'évolution du P&L"""
        trades = self.data.get('trades', pd.DataFrame())
        
        fig = go.Figure()
        
        # P&L par trade
        fig.add_trace(go.Scatter(
            x=trades['timestamp'],
            y=trades['pnl'],
            mode='markers',
            name='PNL per Trade',
            marker=dict(
                color=trades['pnl'],
                colorscale='RdYlGn',
                showscale=True,
                size=8,
            ),
            text=trades['symbol'],
            hovertemplate='<b>%{text}</b><br>Time: %{x}<br>PNL: $%{y:.2f}<extra></extra>'
        ))
        
        # P&L cumulé
        fig.add_trace(go.Scatter(
            x=trades['timestamp'],
            y=trades['pnl'].cumsum(),
            mode='lines',
            name='Cumulative PNL',
            line=dict(color='blue', width=2),
        ))
        
        fig.update_layout(
            title='PNL Evolution',
            xaxis_title='Time',
            yaxis_title='PNL (USD)',
            template='plotly_dark',
            hovermode='x unified',
            height=500,
        )
        
        return self._save_figure(fig, 'pnl_evolution', output_format)
    
    def _plot_win_rate_distribution(self, output_format: str) -> Path:
        """Génère le graphique de distribution du taux de victoire"""
        trades = self.data.get('trades', pd.DataFrame())
        
        # Préparer les données
        data = []
        for symbol in trades['symbol'].unique():
            symbol_trades = trades[trades['symbol'] == symbol]
            win_rate = len(symbol_trades[symbol_trades['pnl'] > 0]) / len(symbol_trades) if len(symbol_trades) > 0 else 0
            data.append({'Symbol': symbol, 'Win Rate': win_rate, 'Trades': len(symbol_trades)})
        
        df = pd.DataFrame(data)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df['Symbol'],
            y=df['Win Rate'],
            text=df['Win Rate'].apply(lambda x: f'{x:.1%}'),
            textposition='auto',
            marker=dict(
                color=df['Win Rate'],
                colorscale='RdYlGn',
                showscale=True,
            ),
            hovertemplate='<b>%{x}</b><br>Win Rate: %{y:.1%}<br>Trades: %{customdata[0]}<extra></extra>',
            customdata=df[['Trades']],
        ))
        
        fig.update_layout(
            title='Win Rate by Symbol',
            xaxis_title='Symbol',
            yaxis_title='Win Rate',
            yaxis_tickformat='.0%',
            template='plotly_dark',
            height=400,
        )
        
        return self._save_figure(fig, 'win_rate_distribution', output_format)
    
    def _plot_strategy_performance(self, output_format: str) -> Path:
        """Génère le graphique de performance par stratégie"""
        performance = self.performance.get('strategy', {})
        
        if not performance:
            return None
        
        strategies = list(performance.keys())
        pnl = [performance[s]['total_pnl'] for s in strategies]
        trades = [performance[s]['total_trades'] for s in strategies]
        win_rate = [performance[s]['win_rate'] for s in strategies]
        
        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=('Total PNL', 'Total Trades', 'Win Rate')
        )
        
        # PNL
        fig.add_trace(
            go.Bar(
                x=strategies,
                y=pnl,
                marker_color=['green' if p > 0 else 'red' for p in pnl],
                text=pnl,
                textposition='auto',
                name='Total PNL',
            ),
            row=1, col=1
        )
        
        # Trades
        fig.add_trace(
            go.Bar(
                x=strategies,
                y=trades,
                marker_color='blue',
                text=trades,
                textposition='auto',
                name='Total Trades',
            ),
            row=1, col=2
        )
        
        # Win Rate
        fig.add_trace(
            go.Bar(
                x=strategies,
                y=win_rate,
                marker_color=win_rate,
                colorscale='RdYlGn',
                text=win_rate,
                textposition='auto',
                name='Win Rate',
            ),
            row=1, col=3
        )
        
        fig.update_layout(
            title='Strategy Performance',
            template='plotly_dark',
            height=400,
            showlegend=False,
        )
        
        return self._save_figure(fig, 'strategy_performance', output_format)
    
    def _plot_symbol_performance(self, output_format: str) -> Path:
        """Génère le graphique de performance par symbole"""
        performance = self.performance.get('symbol', {})
        
        if not performance:
            return None
        
        symbols = list(performance.keys())
        pnl = [performance[s]['total_pnl'] for s in symbols]
        win_rate = [performance[s]['win_rate'] for s in symbols]
        trades = [performance[s]['total_trades'] for s in symbols]
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Total PNL by Symbol', 'Win Rate by Symbol'),
            specs=[[{'secondary_y': True}, {'type': 'bar'}]]
        )
        
        # PNL avec barres
        fig.add_trace(
            go.Bar(
                x=symbols,
                y=pnl,
                marker_color=['green' if p > 0 else 'red' for p in pnl],
                name='Total PNL',
                text=pnl,
                textposition='auto',
            ),
            row=1, col=1
        )
        
        # Trades
        fig.add_trace(
            go.Scatter(
                x=symbols,
                y=trades,
                mode='lines+markers',
                name='Trades',
                line=dict(color='orange', width=2),
                marker=dict(size=10),
                yaxis='y2',
            ),
            row=1, col=1
        )
        
        # Win Rate
        fig.add_trace(
            go.Bar(
                x=symbols,
                y=win_rate,
                marker_color=win_rate,
                colorscale='RdYlGn',
                name='Win Rate',
                text=win_rate,
                textposition='auto',
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title='Symbol Performance',
            template='plotly_dark',
            height=400,
            showlegend=True,
        )
        
        fig.update_yaxes(title_text="PNL (USD)", row=1, col=1)
        fig.update_yaxes(title_text="Trades", secondary_y=True, row=1, col=1)
        fig.update_yaxes(title_text="Win Rate", tickformat='.0%', row=1, col=2)
        
        return self._save_figure(fig, 'symbol_performance', output_format)
    
    def _plot_risk_metrics(self, output_format: str) -> Path:
        """Génère le graphique des métriques de risque"""
        risk = self.performance.get('risk', {})
        
        if not risk:
            return None
        
        metrics = {
            'Sharpe Ratio': risk.get('sharpe_ratio', 0),
            'Sortino Ratio': risk.get('sortino_ratio', 0),
            'Calmar Ratio': risk.get('calmar_ratio', 0),
            'Max Drawdown': risk.get('max_drawdown', 0),
            'VaR 95%': risk.get('var_95', 0),
            'CVaR 95%': risk.get('cvar_95', 0),
        }
        
        fig = go.Figure()
        
        # Radar chart
        fig.add_trace(go.Scatterpolar(
            r=list(metrics.values()),
            theta=list(metrics.keys()),
            fill='toself',
            name='Risk Metrics',
            marker=dict(color='blue'),
        ))
        
        fig.update_layout(
            title='Risk Metrics',
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, max(metrics.values()) * 1.2 if max(metrics.values()) > 0 else 1],
                ),
            ),
            template='plotly_dark',
            height=500,
            showlegend=True,
        )
        
        return self._save_figure(fig, 'risk_metrics', output_format)
    
    def _plot_cumulative_pnl(self, output_format: str) -> Path:
        """Génère le graphique du P&L cumulé"""
        trades = self.data.get('trades', pd.DataFrame())
        
        if trades.empty:
            return None
        
        cum_pnl = trades['pnl'].cumsum()
        
        fig = go.Figure()
        
        # Ligne du P&L cumulé
        fig.add_trace(go.Scatter(
            x=trades['timestamp'],
            y=cum_pnl,
            mode='lines',
            name='Cumulative PNL',
            line=dict(color='blue', width=3),
            fill='tozeroy',
            fillcolor='rgba(0,0,255,0.1)',
        ))
        
        # Zone de drawdown
        running_max = cum_pnl.expanding().max()
        drawdown = (running_max - cum_pnl) / running_max
        
        fig.add_trace(go.Scatter(
            x=trades['timestamp'],
            y=drawdown,
            mode='lines',
            name='Drawdown',
            line=dict(color='red', width=1),
            yaxis='y2',
            fill='tozeroy',
            fillcolor='rgba(255,0,0,0.1)',
        ))
        
        fig.update_layout(
            title='Cumulative PNL and Drawdown',
            xaxis_title='Time',
            yaxis_title='Cumulative PNL (USD)',
            yaxis2=dict(
                title='Drawdown',
                overlaying='y',
                side='right',
                tickformat='.0%',
            ),
            template='plotly_dark',
            hovermode='x unified',
            height=500,
        )
        
        return self._save_figure(fig, 'cumulative_pnl', output_format)
    
    def _plot_opportunity_analysis(self, output_format: str) -> Path:
        """Génère le graphique d'analyse des opportunités"""
        opportunities = self.data.get('opportunities', pd.DataFrame())
        
        if opportunities.empty:
            return None
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Opportunities by Symbol',
                'Execution Rate by Symbol',
                'Average Spread by Symbol',
                'Profit Distribution'
            )
        )
        
        # Opportunités par symbole
        symbol_counts = opportunities['symbol'].value_counts()
        fig.add_trace(
            go.Bar(
                x=symbol_counts.index,
                y=symbol_counts.values,
                marker_color='blue',
                name='Opportunities',
            ),
            row=1, col=1
        )
        
        # Taux d'exécution par symbole
        execution_rate = {}
        for symbol in opportunities['symbol'].unique():
            symbol_opps = opportunities[opportunities['symbol'] == symbol]
            rate = len(symbol_opps[symbol_opps['executed'] == True]) / len(symbol_opps) if len(symbol_opps) > 0 else 0
            execution_rate[symbol] = rate
        
        fig.add_trace(
            go.Bar(
                x=list(execution_rate.keys()),
                y=list(execution_rate.values()),
                marker_color=list(execution_rate.values()),
                colorscale='RdYlGn',
                name='Execution Rate',
                text=list(execution_rate.values()),
                texttemplate='%{text:.1%}',
                textposition='auto',
            ),
            row=1, col=2
        )
        
        # Spread moyen par symbole
        avg_spread = opportunities.groupby('symbol')['spread'].mean()
        fig.add_trace(
            go.Bar(
                x=avg_spread.index,
                y=avg_spread.values,
                marker_color='orange',
                name='Avg Spread',
            ),
            row=2, col=1
        )
        
        # Distribution des profits
        fig.add_trace(
            go.Histogram(
                x=opportunities['profit'],
                nbinsx=30,
                marker_color='green',
                name='Profit Distribution',
                opacity=0.7,
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title='Opportunity Analysis',
            template='plotly_dark',
            height=600,
            showlegend=False,
        )
        
        return self._save_figure(fig, 'opportunity_analysis', output_format)
    
    def _plot_dashboard(self, output_format: str) -> Path:
        """Génère le tableau de bord complet"""
        trades = self.data.get('trades', pd.DataFrame())
        performance = self.performance
        
        fig = make_subplots(
            rows=3, cols=3,
            subplot_titles=(
                'PNL Evolution',
                'Win Rate by Symbol',
                'Performance by Strategy',
                'Risk Metrics',
                'Opportunity Analysis',
                'Symbol Performance',
                'Cumulative PNL',
                'Daily Returns',
                'Summary Stats'
            ),
            specs=[
                [{"type": "scatter"}, {"type": "bar"}, {"type": "bar"}],
                [{"type": "polar"}, {"type": "bar"}, {"type": "bar"}],
                [{"type": "scatter"}, {"type": "bar"}, {"type": "table"}],
            ]
        )
        
        # 1. PNL Evolution
        fig.add_trace(
            go.Scatter(
                x=trades['timestamp'],
                y=trades['pnl'].cumsum(),
                mode='lines',
                name='Cumulative PNL',
                line=dict(color='blue'),
            ),
            row=1, col=1
        )
        
        # 2. Win Rate by Symbol
        if not trades.empty:
            symbols = trades['symbol'].unique()
            win_rates = [
                len(trades[(trades['symbol'] == s) & (trades['pnl'] > 0)]) / len(trades[trades['symbol'] == s])
                for s in symbols
            ]
            fig.add_trace(
                go.Bar(
                    x=symbols,
                    y=win_rates,
                    marker_color=win_rates,
                    colorscale='RdYlGn',
                    name='Win Rate',
                    text=win_rates,
                    texttemplate='%{text:.1%}',
                    textposition='auto',
                ),
                row=1, col=2
            )
        
        # 3. Performance by Strategy
        if 'strategy' in performance:
            strategies = list(performance['strategy'].keys())
            pnl = [performance['strategy'][s]['total_pnl'] for s in strategies]
            fig.add_trace(
                go.Bar(
                    x=strategies,
                    y=pnl,
                    marker_color=['green' if p > 0 else 'red' for p in pnl],
                    name='Strategy PNL',
                    text=pnl,
                    textposition='auto',
                ),
                row=1, col=3
            )
        
        # 4. Risk Metrics
        if 'risk' in performance:
            risk = performance['risk']
            metrics = ['Sharpe', 'Sortino', 'Calmar']
            values = [risk.get('sharpe_ratio', 0), risk.get('sortino_ratio', 0), risk.get('calmar_ratio', 0)]
            fig.add_trace(
                go.Scatterpolar(
                    r=values,
                    theta=metrics,
                    fill='toself',
                    name='Risk Metrics',
                ),
                row=2, col=1
            )
        
        # 5. Opportunity Analysis
        opportunities = self.data.get('opportunities', pd.DataFrame())
        if not opportunities.empty:
            symbol_counts = opportunities['symbol'].value_counts().head(5)
            fig.add_trace(
                go.Bar(
                    x=symbol_counts.index,
                    y=symbol_counts.values,
                    marker_color='blue',
                    name='Opportunities',
                ),
                row=2, col=2
            )
        
        # 6. Symbol Performance
        if 'symbol' in performance:
            symbols = list(performance['symbol'].keys())
            symbol_pnl = [performance['symbol'][s]['total_pnl'] for s in symbols]
            fig.add_trace(
                go.Bar(
                    x=symbols,
                    y=symbol_pnl,
                    marker_color=['green' if p > 0 else 'red' for p in symbol_pnl],
                    name='Symbol PNL',
                    text=symbol_pnl,
                    textposition='auto',
                ),
                row=2, col=3
            )
        
        # 7. Cumulative PNL
        fig.add_trace(
            go.Scatter(
                x=trades['timestamp'],
                y=trades['pnl'].cumsum(),
                mode='lines',
                name='Cumulative PNL',
                line=dict(color='blue', width=2),
            ),
            row=3, col=1
        )
        
        # 8. Daily Returns
        if not trades.empty:
            daily_returns = trades.groupby(trades['timestamp'].dt.date)['pnl'].sum()
            fig.add_trace(
                go.Bar(
                    x=[str(d) for d in daily_returns.index],
                    y=daily_returns.values,
                    marker_color=['green' if v > 0 else 'red' for v in daily_returns.values],
                    name='Daily Returns',
                ),
                row=3, col=2
            )
        
        # 9. Summary Stats (Table)
        if 'summary' in performance:
            summary = performance['summary']
            header = ['Metric', 'Value']
            cells = [
                ['Total Trades', 'Total PNL', 'Avg PNL', 'Win Rate', 'Max PNL', 'Min PNL'],
                [
                    summary.get('total_trades', 0),
                    f"${summary.get('total_pnl', 0):.2f}",
                    f"${summary.get('avg_pnl', 0):.2f}",
                    f"{summary.get('win_rate', 0)*100:.1f}%",
                    f"${summary.get('max_pnl', 0):.2f}",
                    f"${summary.get('min_pnl', 0):.2f}",
                ]
            ]
            fig.add_trace(
                go.Table(
                    header=dict(values=header, fill_color='paleturquoise', align='left'),
                    cells=dict(values=cells, fill_color='lavender', align='left'),
                    name='Summary',
                ),
                row=3, col=3
            )
        
        fig.update_layout(
            title='Arbitrage Bot Dashboard',
            template='plotly_dark',
            height=1000,
            showlegend=False,
        )
        
        return self._save_figure(fig, 'dashboard', output_format)
    
    def _save_figure(self, fig: go.Figure, name: str, output_format: str) -> Path:
        """Sauvegarde une figure"""
        output_path = self.output_dir / f"{name}.{output_format}"
        
        if output_format == 'html':
            fig.write_html(str(output_path))
        elif output_format == 'png':
            fig.write_image(str(output_path), scale=2)
        elif output_format == 'pdf':
            fig.write_image(str(output_path), format='pdf')
        else:
            fig.write_html(str(output_path))
        
        return output_path
    
    # ============================================================
    # REPORT GENERATION
    # ============================================================
    
    def generate_report(self, output_format: str = 'html') -> Path:
        """
        Génère un rapport complet
        
        Args:
            output_format: Format de sortie ('html', 'pdf', 'json')
            
        Returns:
            Path: Chemin du rapport généré
        """
        logger.info(f"Generating report in {output_format} format...")
        
        if not self.performance:
            self.analyze_performance()
        
        if not self.data:
            self.load_data()
        
        # Générer les visualisations
        self.generate_visualizations('html' if output_format == 'html' else 'png')
        
        # Créer le rapport
        if output_format == 'html':
            report_path = self._generate_html_report()
        elif output_format == 'pdf':
            report_path = self._generate_pdf_report()
        elif output_format == 'json':
            report_path = self._generate_json_report()
        else:
            report_path = self._generate_html_report()
        
        logger.info(f"Report generated: {report_path}")
        return report_path
    
    def _generate_html_report(self) -> Path:
        """Génère un rapport HTML"""
        import jinja2
        
        # Charger le template
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NEXUS Arbitrage Bot Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #1a1a2e; color: #e0e0e0; }
                h1 { color: #00d4aa; border-bottom: 2px solid #00d4aa; padding-bottom: 10px; }
                h2 { color: #00d4aa; margin-top: 30px; }
                .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
                .card { background: #16213e; padding: 20px; border-radius: 10px; border: 1px solid #0f3460; }
                .card .value { font-size: 24px; font-weight: bold; color: #00d4aa; }
                .card .label { font-size: 14px; color: #a0a0a0; }
                .chart { margin: 30px 0; border: 1px solid #0f3460; border-radius: 10px; overflow: hidden; }
                .chart iframe { width: 100%; height: 500px; border: none; }
                .footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #0f3460; text-align: center; color: #a0a0a0; }
            </style>
        </head>
        <body>
            <h1>🚀 NEXUS Arbitrage Bot Report</h1>
            <p>Generated: {{ timestamp }}</p>
            
            <h2>📊 Performance Summary</h2>
            <div class="summary">
                <div class="card">
                    <div class="value">{{ summary.total_trades }}</div>
                    <div class="label">Total Trades</div>
                </div>
                <div class="card">
                    <div class="value">${{ "%.2f"|format(summary.total_pnl) }}</div>
                    <div class="label">Total PNL</div>
                </div>
                <div class="card">
                    <div class="value">{{ "%.1f"|format(summary.win_rate * 100) }}%</div>
                    <div class="label">Win Rate</div>
                </div>
                <div class="card">
                    <div class="value">{{ "%.2f"|format(risk.sharpe_ratio) }}</div>
                    <div class="label">Sharpe Ratio</div>
                </div>
                <div class="card">
                    <div class="value">{{ "%.1f"|format(risk.max_drawdown * 100) }}%</div>
                    <div class="label">Max Drawdown</div>
                </div>
            </div>
            
            <h2>📈 Charts</h2>
            {% for chart in charts %}
            <div class="chart">
                <iframe src="{{ chart }}"></iframe>
            </div>
            {% endfor %}
            
            <div class="footer">
                <p>NEXUS Arbitrage Bot v2.0.0 | Copyright © 2026 NEXUS QUANTUM LTD</p>
            </div>
        </body>
        </html>
        """
        
        # Préparer les données
        summary = self.performance.get('summary', {})
        risk = self.performance.get('risk', {})
        
        # Récupérer les chemins des charts
        chart_files = []
        for file in self.output_dir.glob("*.html"):
            chart_files.append(str(file.name))
        
        # Remplacer les variables
        html = template_str
        html = html.replace("{{ timestamp }}", datetime.now().isoformat())
        html = html.replace("{{ summary.total_trades }}", str(summary.get('total_trades', 0)))
        html = html.replace("{{ summary.total_pnl }}", f"{summary.get('total_pnl', 0):.2f}")
        html = html.replace("{{ summary.win_rate * 100 }}", f"{summary.get('win_rate', 0) * 100:.1f}")
        html = html.replace("{{ risk.sharpe_ratio }}", f"{risk.get('sharpe_ratio', 0):.2f}")
        html = html.replace("{{ risk.max_drawdown * 100 }}", f"{risk.get('max_drawdown', 0) * 100:.1f}")
        
        # Ajouter les charts
        charts_html = ""
        for chart in chart_files:
            charts_html += f'<div class="chart"><iframe src="{chart}"></iframe></div>\n'
        html = html.replace("{% for chart in charts %}", charts_html)
        html = html.replace("{% endfor %}", "")
        
        # Sauvegarder
        report_path = self.output_dir / "report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return report_path
    
    def _generate_pdf_report(self) -> Path:
        """Génère un rapport PDF"""
        # Pour le PDF, on utilise d'abord HTML puis on convertit
        html_path = self._generate_html_report()
        pdf_path = self.output_dir / "report.pdf"
        
        try:
            import pdfkit
            pdfkit.from_file(str(html_path), str(pdf_path))
        except ImportError:
            logger.warning("pdfkit not installed, generating HTML report instead")
            return html_path
        
        return pdf_path
    
    def _generate_json_report(self) -> Path:
        """Génère un rapport JSON"""
        report = {
            'metadata': {
                'version': '2.0.0',
                'timestamp': datetime.now().isoformat(),
                'generated_by': 'ArbitrageBotAnalyzer',
            },
            'performance': self.performance,
            'data': {
                'trades_count': len(self.data.get('trades', pd.DataFrame())),
                'positions_count': len(self.data.get('positions', pd.DataFrame())),
                'opportunities_count': len(self.data.get('opportunities', pd.DataFrame())),
            }
        }
        
        report_path = self.output_dir / "report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report_path
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def export_data(self, format: str = 'csv') -> Dict[str, Path]:
        """
        Exporte les données
        
        Args:
            format: Format de sortie ('csv', 'json', 'parquet')
            
        Returns:
            Dict[str, Path]: Chemins des fichiers exportés
        """
        logger.info(f"Exporting data in {format} format...")
        
        files = {}
        export_dir = self.output_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        for name, data in self.data.items():
            if data.empty:
                continue
            
            file_path = export_dir / f"{name}.{format}"
            
            if format == 'csv':
                data.to_csv(file_path, index=False)
            elif format == 'json':
                data.to_json(file_path, orient='records', indent=2)
            elif format == 'parquet':
                data.to_parquet(file_path)
            else:
                data.to_csv(file_path, index=False)
            
            files[name] = file_path
        
        return files

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Analyzer")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-s", "--start",
        help="Start date (YYYY-MM-DD)",
        default=None
    )
    parser.add_argument(
        "-e", "--end",
        help="End date (YYYY-MM-DD)",
        default=None
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory",
        default="reports"
    )
    parser.add_argument(
        "-f", "--format",
        help="Output format (html, pdf, json)",
        default="html"
    )
    parser.add_argument(
        "--no-viz",
        help="Skip visualizations",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Créer l'analyseur
    analyzer = ArbitrageBotAnalyzer(
        config_path=args.config,
        output_dir=args.output
    )
    
    # Charger les données
    analyzer.load_data(
        start_date=args.start,
        end_date=args.end
    )
    
    # Analyser
    analyzer.analyze_performance()
    analyzer.analyze_opportunities()
    
    # Générer les visualisations
    if not args.no_viz:
        analyzer.generate_visualizations()
    
    # Générer le rapport
    report_path = analyzer.generate_report(args.format)
    print(f"Report generated: {report_path}")

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotAnalyzer',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

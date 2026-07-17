# trading/bots/ai_bot/ai_bot_dashboard.py
"""
NEXUS AI TRADING SYSTEM - Dashboard Interface
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements the dashboard interface for the AI Trading Bot.
Provides:
    - Real-time performance visualization
    - Trading activity monitoring
    - Position and portfolio management
    - Risk metrics display
    - System health monitoring
    - Interactive charts and graphs
    - Customizable widgets
    - Alert management
    - Strategy performance tracking
    - Historical data analysis
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, State, callback, ctx
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
import websocket

# Import bot components
from trading.bots.ai_bot.ai_bot import AIBot, BotStatus, BotMode
from trading.bots.ai_bot.ai_bot_api import AIBotAPI
from trading.bots.ai_bot.monitoring import MetricsCollector, HealthChecker
from trading.bots.ai_bot.position_manager import PositionManager
from trading.bots.ai_bot.performance_tracker import PerformanceTracker

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class DashboardTheme(Enum):
    """Dashboard theme enumeration."""
    LIGHT = "light"
    DARK = "dark"
    NEXUS = "nexus"


class WidgetType(Enum):
    """Dashboard widget types."""
    CHART = "chart"
    METRIC = "metric"
    TABLE = "table"
    STATUS = "status"
    ALERT = "alert"
    PORTFOLIO = "portfolio"
    TRADES = "trades"
    HEALTH = "health"
    PERFORMANCE = "performance"
    RISK = "risk"
    STRATEGY = "strategy"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    theme: DashboardTheme = DashboardTheme.NEXUS
    refresh_interval: int = 5000  # milliseconds
    show_advanced: bool = False
    auto_update: bool = True
    language: str = "en"
    timezone: str = "UTC"
    charts: List[str] = field(default_factory=lambda: ['equity', 'drawdown', 'returns'])
    widgets: List[str] = field(default_factory=lambda: ['metrics', 'positions', 'trades', 'health'])


@dataclass
class DashboardWidget:
    """Dashboard widget definition."""
    id: str
    type: WidgetType
    title: str
    position: int
    config: Dict[str, Any] = field(default_factory=dict)
    data: Any = None
    size: str = "col-6"


# =============================================================================
# Dashboard Class
# =============================================================================

class AIBotDashboard:
    """
    Interactive dashboard for AI Trading Bot monitoring and management.
    
    This class provides a web-based dashboard built with Dash and Plotly,
    offering real-time visualization, monitoring, and control of the AI
    trading bot.
    
    Features:
        - Real-time performance charts
        - Portfolio and position tracking
        - Risk metrics visualization
        - System health monitoring
        - Trade history viewer
        - Strategy performance analysis
        - Interactive controls
        - Customizable layouts
    
    Usage:
        # Create dashboard
        dashboard = AIBotDashboard(bot)
        
        # Run dashboard server
        dashboard.run(debug=True, port=8050)
    """
    
    def __init__(
        self,
        bot: Optional[AIBot] = None,
        api: Optional[AIBotAPI] = None,
        config: Optional[Union[Dict[str, Any], DashboardConfig]] = None,
        debug: bool = False
    ):
        """
        Initialize the dashboard.
        
        Args:
            bot: AI Bot instance
            api: AI Bot API instance
            config: Dashboard configuration
            debug: Run in debug mode
        """
        # Store references
        self.bot = bot
        self.api = api
        
        # Load configuration
        if isinstance(config, dict):
            self.config = DashboardConfig(**config)
        elif isinstance(config, DashboardConfig):
            self.config = config
        else:
            self.config = DashboardConfig()
        
        # Initialize Dash app
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[
                dbc.themes.DARKLY,
                dbc.themes.BOOTSTRAP,
            ],
            external_scripts=[
                "https://cdn.plot.ly/plotly-latest.min.js",
            ],
            title="NEXUS AI Trading Bot Dashboard",
            update_title="Updating...",
        )
        
        # App state
        self.app_state = {
            'last_update': None,
            'theme': self.config.theme.value,
            'auto_update': self.config.auto_update,
            'selected_symbol': None,
            'selected_timeframe': '1h',
            'refresh_interval': self.config.refresh_interval
        }
        
        # Data cache
        self.cache = {
            'metrics': None,
            'positions': None,
            'trades': None,
            'health': None,
            'performance': None
        }
        
        # WebSocket connection
        self.ws_connected = False
        self.ws_thread = None
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Setup layout
        self._setup_layout()
        self._setup_callbacks()
        
        self.logger.info("Dashboard initialized")
    
    # =========================================================================
    # Layout Setup
    # =========================================================================
    
    def _setup_layout(self) -> None:
        """Setup the dashboard layout."""
        self.app.layout = html.Div([
            # Header
            self._create_header(),
            
            # Main content
            dbc.Container([
                # Navigation tabs
                self._create_tabs(),
                
                # Content area
                html.Div(id='dashboard-content'),
                
                # Hidden divs for data storage
                html.Div(id='store-metrics', style={'display': 'none'}),
                html.Div(id='store-positions', style={'display': 'none'}),
                html.Div(id='store-trades', style={'display': 'none'}),
                html.Div(id='store-health', style={'display': 'none'}),
                
                # Refresh interval
                dcc.Interval(
                    id='interval-component',
                    interval=self.config.refresh_interval,
                    n_intervals=0
                ),
                
                # WebSocket connection
                html.Div(id='websocket-status', style={'display': 'none'})
            ], fluid=True),
        ], className='nexus-dashboard')
    
    def _create_header(self) -> html.Div:
        """Create dashboard header."""
        return html.Div([
            dbc.Navbar([
                dbc.Container([
                    # Logo and brand
                    dbc.Row([
                        dbc.Col([
                            html.Img(
                                src='/assets/nexus-logo.png',
                                height='40px',
                                className='d-inline-block align-top'
                            ),
                            html.Span(
                                'NEXUS AI Trading Bot',
                                className='navbar-brand ms-2 h3'
                            )
                        ], width='auto')
                    ], align='center'),
                    
                    # Status and controls
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Span('Status: ', className='me-1'),
                                html.Span(id='bot-status-badge', className='badge bg-success'),
                                html.Button(
                                    'Start',
                                    id='btn-start',
                                    className='btn btn-sm btn-primary ms-2'
                                ),
                                html.Button(
                                    'Stop',
                                    id='btn-stop',
                                    className='btn btn-sm btn-danger ms-1'
                                ),
                                html.Button(
                                    'Pause',
                                    id='btn-pause',
                                    className='btn btn-sm btn-warning ms-1'
                                ),
                                html.Button(
                                    'Resume',
                                    id='btn-resume',
                                    className='btn btn-sm btn-info ms-1'
                                ),
                                html.Span('|', className='ms-2 me-2'),
                                html.Span('Mode: ', className='me-1'),
                                html.Span(id='bot-mode-badge', className='badge bg-secondary'),
                            ], className='d-flex align-items-center')
                        ], width='auto')
                    ], align='center'),
                    
                    # Theme toggle
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                html.I(className='fas fa-moon'),
                                id='btn-theme-toggle',
                                color='light',
                                size='sm',
                                className='ms-2'
                            )
                        ], width='auto')
                    ])
                ])
            ], color='dark', dark=True)
        ])
    
    def _create_tabs(self) -> dbc.Tabs:
        """Create navigation tabs."""
        return dbc.Tabs([
            dbc.Tab(label='Overview', tab_id='tab-overview'),
            dbc.Tab(label='Performance', tab_id='tab-performance'),
            dbc.Tab(label='Portfolio', tab_id='tab-portfolio'),
            dbc.Tab(label='Risk', tab_id='tab-risk'),
            dbc.Tab(label='Trades', tab_id='tab-trades'),
            dbc.Tab(label='Strategies', tab_id='tab-strategies'),
            dbc.Tab(label='System', tab_id='tab-system'),
            dbc.Tab(label='Settings', tab_id='tab-settings'),
        ], id='tabs', active_tab='tab-overview')
    
    # =========================================================================
    # Content Creation Methods
    # =========================================================================
    
    def _create_overview_content(self) -> html.Div:
        """Create overview tab content."""
        return html.Div([
            dbc.Row([
                # Metrics cards
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5('Total PnL', className='card-title text-muted'),
                            html.H2(id='metric-total-pnl', children='$0.00'),
                            html.Small('All time', className='text-muted')
                        ])
                    ], className='metric-card shadow-sm mb-3')
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5('Win Rate', className='card-title text-muted'),
                            html.H2(id='metric-win-rate', children='0%'),
                            html.Small('Last 100 trades', className='text-muted')
                        ])
                    ], className='metric-card shadow-sm mb-3')
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5('Sharpe Ratio', className='card-title text-muted'),
                            html.H2(id='metric-sharpe', children='0.00'),
                            html.Small('Risk-adjusted return', className='text-muted')
                        ])
                    ], className='metric-card shadow-sm mb-3')
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5('Max Drawdown', className='card-title text-muted'),
                            html.H2(id='metric-drawdown', children='0%'),
                            html.Small('All time', className='text-muted')
                        ])
                    ], className='metric-card shadow-sm mb-3')
                ], width=3)
            ]),
            
            # Charts row
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Equity Curve'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-equity', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Drawdown'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-drawdown', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ]),
            
            # Second charts row
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Daily Returns'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-returns', className='w-100', style={'height': '350px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Risk Metrics'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-risk', className='w-100', style={'height': '350px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ])
        ])
    
    def _create_performance_content(self) -> html.Div:
        """Create performance tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Performance Metrics'),
                        dbc.CardBody([
                            html.Div(id='performance-metrics-table')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Returns Distribution'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-returns-distribution', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Performance Summary'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-performance-summary', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ])
        ])
    
    def _create_portfolio_content(self) -> html.Div:
        """Create portfolio tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Portfolio Allocation'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-portfolio-allocation', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Positions'),
                        dbc.CardBody([
                            html.Div(id='positions-table')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Portfolio Performance'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-portfolio-performance', className='w-100', style={'height': '350px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ])
        ])
    
    def _create_risk_content(self) -> html.Div:
        """Create risk tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Risk Metrics'),
                        dbc.CardBody([
                            html.Div(id='risk-metrics-table')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Risk Heatmap'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-risk-heatmap', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Risk-Adjusted Returns'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-risk-adjusted', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ])
        ])
    
    def _create_trades_content(self) -> html.Div:
        """Create trades tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Recent Trades'),
                        dbc.CardBody([
                            html.Div(id='trades-table')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Trade Volume'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-trade-volume', className='w-100', style={'height': '350px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Trade Distribution'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-trade-distribution', className='w-100', style={'height': '350px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ])
        ])
    
    def _create_strategies_content(self) -> html.Div:
        """Create strategies tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Strategy Performance'),
                        dbc.CardBody([
                            dcc.Graph(id='chart-strategy-performance', className='w-100', style={'height': '400px'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Active Strategies'),
                        dbc.CardBody([
                            html.Div(id='strategies-table')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ])
        ])
    
    def _create_system_content(self) -> html.Div:
        """Create system tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('System Health'),
                        dbc.CardBody([
                            html.Div(id='system-health-display')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('System Metrics'),
                        dbc.CardBody([
                            html.Div(id='system-metrics-display')
                        ])
                    ], className='shadow-sm mb-3')
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Logs'),
                        dbc.CardBody([
                            html.Div(id='logs-display', style={'height': '300px', 'overflow-y': 'scroll'})
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ])
        ])
    
    def _create_settings_content(self) -> html.Div:
        """Create settings tab content."""
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader('Dashboard Settings'),
                        dbc.CardBody([
                            dbc.Form([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label('Refresh Interval (ms)'),
                                        dbc.Input(
                                            type='number',
                                            id='settings-refresh-interval',
                                            value=self.config.refresh_interval,
                                            min=1000,
                                            max=30000,
                                            step=1000
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Label('Theme'),
                                        dbc.Select(
                                            id='settings-theme',
                                            options=[
                                                {'label': 'Light', 'value': 'light'},
                                                {'label': 'Dark', 'value': 'dark'},
                                                {'label': 'NEXUS', 'value': 'nexus'}
                                            ],
                                            value=self.config.theme.value
                                        )
                                    ], width=6)
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label('Auto Update'),
                                        dbc.Switch(
                                            id='settings-auto-update',
                                            value=self.config.auto_update
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Label('Show Advanced'),
                                        dbc.Switch(
                                            id='settings-show-advanced',
                                            value=self.config.show_advanced
                                        )
                                    ], width=6)
                                ]),
                                html.Hr(),
                                dbc.Button(
                                    'Save Settings',
                                    id='btn-save-settings',
                                    color='primary',
                                    className='mt-2'
                                ),
                                dbc.Alert(
                                    'Settings saved!',
                                    id='alert-settings-saved',
                                    color='success',
                                    dismissible=True,
                                    is_open=False,
                                    className='mt-2'
                                )
                            ])
                        ])
                    ], className='shadow-sm mb-3')
                ], width=12)
            ])
        ])
    
    # =========================================================================
    # Callback Setup
    # =========================================================================
    
    def _setup_callbacks(self) -> None:
        """Setup Dash callbacks."""
        
        # Tab content switching
        @self.app.callback(
            Output('dashboard-content', 'children'),
            Input('tabs', 'active_tab')
        )
        def switch_tab(tab):
            """Switch dashboard tab."""
            if tab == 'tab-overview':
                return self._create_overview_content()
            elif tab == 'tab-performance':
                return self._create_performance_content()
            elif tab == 'tab-portfolio':
                return self._create_portfolio_content()
            elif tab == 'tab-risk':
                return self._create_risk_content()
            elif tab == 'tab-trades':
                return self._create_trades_content()
            elif tab == 'tab-strategies':
                return self._create_strategies_content()
            elif tab == 'tab-system':
                return self._create_system_content()
            elif tab == 'tab-settings':
                return self._create_settings_content()
            else:
                return html.Div()
        
        # Update data on interval
        @self.app.callback(
            [
                Output('store-metrics', 'children'),
                Output('store-positions', 'children'),
                Output('store-trades', 'children'),
                Output('store-health', 'children'),
                Output('bot-status-badge', 'children'),
                Output('bot-status-badge', 'className'),
                Output('bot-mode-badge', 'children'),
            ],
            Input('interval-component', 'n_intervals')
        )
        def update_data(n_intervals):
            """Update dashboard data."""
            if not self.bot:
                return None, None, None, None, 'No Bot', 'badge bg-secondary', 'N/A'
            
            try:
                # Get metrics
                metrics = self.bot.get_metrics()
                self.cache['metrics'] = metrics
                
                # Get positions
                positions = self.bot.get_positions()
                self.cache['positions'] = positions
                
                # Get trades
                trades = self.bot.get_trade_history(100)
                self.cache['trades'] = trades
                
                # Get health
                health = self.bot.get_status()
                self.cache['health'] = health
                
                # Get status
                status = health.get('status', 'unknown')
                status_class = {
                    'running': 'badge bg-success',
                    'stopped': 'badge bg-secondary',
                    'paused': 'badge bg-warning',
                    'error': 'badge bg-danger'
                }.get(status, 'badge bg-secondary')
                
                # Get mode
                mode = health.get('mode', 'N/A')
                
                return (
                    json.dumps(metrics),
                    json.dumps(positions),
                    json.dumps(trades),
                    json.dumps(health),
                    status.capitalize(),
                    status_class,
                    mode
                )
                
            except Exception as e:
                self.logger.error(f"Error updating data: {e}")
                return None, None, None, None, 'Error', 'badge bg-danger', 'N/A'
        
        # Update overview metrics
        @self.app.callback(
            [
                Output('metric-total-pnl', 'children'),
                Output('metric-win-rate', 'children'),
                Output('metric-sharpe', 'children'),
                Output('metric-drawdown', 'children'),
            ],
            Input('store-metrics', 'children')
        )
        def update_metrics(metrics_json):
            """Update overview metrics."""
            if not metrics_json:
                return '$0.00', '0%', '0.00', '0%'
            
            try:
                metrics = json.loads(metrics_json)
                total_pnl = metrics.get('total_pnl', 0)
                win_rate = metrics.get('win_rate', 0) * 100
                sharpe = metrics.get('sharpe_ratio', 0)
                drawdown = metrics.get('max_drawdown', 0) * 100
                
                return (
                    f'${total_pnl:,.2f}',
                    f'{win_rate:.1f}%',
                    f'{sharpe:.2f}',
                    f'{drawdown:.1f}%'
                )
            except Exception as e:
                self.logger.error(f"Error parsing metrics: {e}")
                return '$0.00', '0%', '0.00', '0%'
        
        # Update equity chart
        @self.app.callback(
            Output('chart-equity', 'figure'),
            Input('store-metrics', 'children')
        )
        def update_equity_chart(metrics_json):
            """Update equity curve chart."""
            fig = go.Figure()
            
            if not metrics_json or not self.bot:
                fig.add_annotation(text='No data available', showarrow=False)
                fig.update_layout(
                    template='plotly_dark',
                    xaxis_title='Time',
                    yaxis_title='Equity'
                )
                return fig
            
            try:
                # Get equity data
                if hasattr(self.bot, 'performance_tracker'):
                    equity_curve = self.bot.performance_tracker.get_equity_curve()
                    if equity_curve is not None and not equity_curve.empty:
                        fig.add_trace(go.Scatter(
                            x=equity_curve.index,
                            y=equity_curve.values,
                            mode='lines',
                            name='Equity',
                            line=dict(color='#00ff88', width=2)
                        ))
                        
                        # Add horizontal line for initial capital
                        initial_capital = self.bot.config.initial_capital
                        fig.add_hline(
                            y=initial_capital,
                            line_dash='dash',
                            line_color='gray',
                            annotation_text='Initial Capital'
                        )
                        
                        fig.update_layout(
                            template='plotly_dark',
                            xaxis_title='Time',
                            yaxis_title='Equity ($)',
                            hovermode='x',
                            showlegend=True
                        )
                    else:
                        fig.add_annotation(text='No equity data available', showarrow=False)
            except Exception as e:
                self.logger.error(f"Error updating equity chart: {e}")
                fig.add_annotation(text=f'Error: {str(e)}', showarrow=False)
            
            return fig
        
        # Update drawdown chart
        @self.app.callback(
            Output('chart-drawdown', 'figure'),
            Input('store-metrics', 'children')
        )
        def update_drawdown_chart(metrics_json):
            """Update drawdown chart."""
            fig = go.Figure()
            
            if not metrics_json or not self.bot:
                fig.add_annotation(text='No data available', showarrow=False)
                fig.update_layout(template='plotly_dark')
                return fig
            
            try:
                if hasattr(self.bot, 'performance_tracker'):
                    drawdown = self.bot.performance_tracker.get_drawdown()
                    if drawdown is not None and not drawdown.empty:
                        fig.add_trace(go.Scatter(
                            x=drawdown.index,
                            y=drawdown.values * 100,
                            fill='tozeroy',
                            name='Drawdown',
                            line=dict(color='#ff4444', width=1),
                            fillcolor='rgba(255, 68, 68, 0.2)'
                        ))
                        
                        fig.update_layout(
                            template='plotly_dark',
                            xaxis_title='Time',
                            yaxis_title='Drawdown (%)',
                            hovermode='x',
                            yaxis=dict(range=[-100, 0])
                        )
                    else:
                        fig.add_annotation(text='No drawdown data available', showarrow=False)
            except Exception as e:
                self.logger.error(f"Error updating drawdown chart: {e}")
                fig.add_annotation(text=f'Error: {str(e)}', showarrow=False)
            
            return fig
        
        # Update positions table
        @self.app.callback(
            Output('positions-table', 'children'),
            Input('store-positions', 'children')
        )
        def update_positions_table(positions_json):
            """Update positions table."""
            if not positions_json:
                return html.Div('No positions', className='text-muted')
            
            try:
                positions = json.loads(positions_json)
                if not positions:
                    return html.Div('No open positions', className='text-muted')
                
                # Create table
                table = dbc.Table([
                    html.Thead(html.Tr([
                        html.Th('Symbol'),
                        html.Th('Side'),
                        html.Th('Entry Price'),
                        html.Th('Current Price'),
                        html.Th('Quantity'),
                        html.Th('PnL'),
                        html.Th('PnL %'),
                        html.Th('Status')
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(pos.get('symbol', 'N/A')),
                            html.Td(
                                pos.get('side', 'N/A'),
                                className='text-success' if pos.get('side') == 'buy' else 'text-danger'
                            ),
                            html.Td(f"${pos.get('entry_price', 0):,.2f}"),
                            html.Td(f"${pos.get('current_price', 0):,.2f}"),
                            html.Td(f"{pos.get('quantity', 0):,.4f}"),
                            html.Td(
                                f"${pos.get('pnl', 0):,.2f}",
                                className='text-success' if pos.get('pnl', 0) >= 0 else 'text-danger'
                            ),
                            html.Td(
                                f"{pos.get('pnl_percent', 0):,.2f}%",
                                className='text-success' if pos.get('pnl_percent', 0) >= 0 else 'text-danger'
                            ),
                            html.Td(pos.get('status', 'N/A'))
                        ]) for pos in positions
                    ])
                ], bordered=True, dark=True, hover=True, responsive=True, striped=True)
                
                return table
                
            except Exception as e:
                self.logger.error(f"Error updating positions table: {e}")
                return html.Div(f'Error: {str(e)}', className='text-danger')
        
        # Bot control callbacks
        @self.app.callback(
            Output('btn-start', 'disabled'),
            Output('btn-stop', 'disabled'),
            Output('btn-pause', 'disabled'),
            Output('btn-resume', 'disabled'),
            Input('bot-status-badge', 'children')
        )
        def update_controls(status):
            """Update control button states."""
            status_lower = status.lower() if status else 'unknown'
            
            start_disabled = status_lower in ['running', 'starting']
            stop_disabled = status_lower in ['stopped', 'stopping', 'unknown']
            pause_disabled = status_lower not in ['running']
            resume_disabled = status_lower != 'paused'
            
            return start_disabled, stop_disabled, pause_disabled, resume_disabled
        
        @self.app.callback(
            [
                Output('bot-status-badge', 'children', allow_duplicate=True),
                Output('bot-status-badge', 'className', allow_duplicate=True),
                Output('alert-settings-saved', 'is_open', allow_duplicate=True)
            ],
            [
                Input('btn-start', 'n_clicks'),
                Input('btn-stop', 'n_clicks'),
                Input('btn-pause', 'n_clicks'),
                Input('btn-resume', 'n_clicks'),
            ],
            prevent_initial_call=True
        )
        def handle_bot_controls(start_clicks, stop_clicks, pause_clicks, resume_clicks):
            """Handle bot control button clicks."""
            if not self.bot:
                return 'No Bot', 'badge bg-secondary', False
            
            try:
                trigger_id = ctx.triggered_id
                
                if trigger_id == 'btn-start':
                    if self.bot.status != BotStatus.RUNNING:
                        asyncio.run(self.bot.start())
                        return 'Starting...', 'badge bg-warning', False
                
                elif trigger_id == 'btn-stop':
                    if self.bot.status != BotStatus.STOPPED:
                        asyncio.run(self.bot.stop())
                        return 'Stopping...', 'badge bg-warning', False
                
                elif trigger_id == 'btn-pause':
                    if self.bot.status == BotStatus.RUNNING:
                        asyncio.run(self.bot.pause())
                        return 'Pausing...', 'badge bg-warning', False
                
                elif trigger_id == 'btn-resume':
                    if self.bot.status == BotStatus.PAUSED:
                        asyncio.run(self.bot.resume())
                        return 'Resuming...', 'badge bg-warning', False
                
                return None, None, False
                
            except Exception as e:
                self.logger.error(f"Error handling bot control: {e}")
                return 'Error', 'badge bg-danger', False
        
        # Settings callbacks
        @self.app.callback(
            Output('alert-settings-saved', 'is_open'),
            Input('btn-save-settings', 'n_clicks'),
            [
                State('settings-refresh-interval', 'value'),
                State('settings-theme', 'value'),
                State('settings-auto-update', 'value'),
                State('settings-show-advanced', 'value')
            ]
        )
        def save_settings(n_clicks, refresh_interval, theme, auto_update, show_advanced):
            """Save dashboard settings."""
            if not n_clicks:
                return False
            
            try:
                # Update config
                self.config.refresh_interval = refresh_interval
                self.config.theme = DashboardTheme(theme)
                self.config.auto_update = auto_update
                self.config.show_advanced = show_advanced
                
                # Update interval
                self.app_state['refresh_interval'] = refresh_interval
                self.app_state['auto_update'] = auto_update
                
                # Update interval component
                # This would require using a hidden component or reassigning
                
                self.logger.info("Dashboard settings saved")
                return True
                
            except Exception as e:
                self.logger.error(f"Error saving settings: {e}")
                return False
    
    # =========================================================================
    # Run Methods
    # =========================================================================
    
    def run(
        self,
        host: str = '0.0.0.0',
        port: int = 8050,
        debug: bool = False,
        dev_tools_hot_reload: bool = True,
        **kwargs
    ) -> None:
        """
        Run the dashboard server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            debug: Run in debug mode
            dev_tools_hot_reload: Enable hot reload
            **kwargs: Additional arguments for app.run_server
        """
        self.logger.info(f"Starting dashboard on {host}:{port}")
        
        self.app.run_server(
            host=host,
            port=port,
            debug=debug,
            dev_tools_hot_reload=dev_tools_hot_reload,
            **kwargs
        )
    
    def run_async(self) -> None:
        """Run the dashboard server asynchronously."""
        import threading
        
        def run_server():
            self.run()
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        self.logger.info("Dashboard started in background thread")
    
    # =========================================================================
    # WebSocket Integration
    # =========================================================================
    
    def connect_websocket(self, url: str) -> None:
        """
        Connect to WebSocket for real-time updates.
        
        Args:
            url: WebSocket URL
        """
        try:
            ws = websocket.WebSocketApp(
                url,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close
            )
            
            import threading
            self.ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
            self.ws_thread.start()
            self.ws_connected = True
            
            self.logger.info(f"WebSocket connected to {url}")
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
    
    def _on_ws_message(self, message: str) -> None:
        """Handle WebSocket message."""
        try:
            data = json.loads(message)
            self.logger.debug(f"WebSocket message received: {data.get('type')}")
            
            # Update cache based on message type
            if data.get('type') == 'status':
                self.cache['health'] = data.get('data')
            elif data.get('type') == 'position':
                self.cache['positions'] = data.get('data')
            elif data.get('type') == 'metrics':
                self.cache['metrics'] = data.get('data')
            
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_ws_error(self, error: Exception) -> None:
        """Handle WebSocket error."""
        self.logger.error(f"WebSocket error: {error}")
    
    def _on_ws_close(self, close_status_code: int, close_msg: str) -> None:
        """Handle WebSocket close."""
        self.ws_connected = False
        self.logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")


# =============================================================================
# Factory Function
# =============================================================================

def create_dashboard(
    bot: Optional[AIBot] = None,
    api: Optional[AIBotAPI] = None,
    config: Optional[Union[Dict[str, Any], DashboardConfig]] = None,
    debug: bool = False,
    host: str = '0.0.0.0',
    port: int = 8050
) -> AIBotDashboard:
    """
    Factory function to create and run the dashboard.
    
    Args:
        bot: AI Bot instance
        api: AI Bot API instance
        config: Dashboard configuration
        debug: Run in debug mode
        host: Host to bind to
        port: Port to bind to
        
    Returns:
        AIBotDashboard instance
    """
    dashboard = AIBotDashboard(bot=bot, api=api, config=config, debug=debug)
    dashboard.run(host=host, port=port, debug=debug)
    return dashboard


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'AIBotDashboard',
    'DashboardConfig',
    'DashboardWidget',
    'DashboardTheme',
    'WidgetType',
    'create_dashboard'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot Dashboard

This module provides an interactive web-based dashboard for monitoring
and managing the NEXUS AI Trading Bot.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Features:
    - Real-time performance monitoring
    - Interactive charts and visualizations
    - Portfolio and position management
    - Risk metrics display
    - System health monitoring
    - Trade history viewer
    - Strategy performance tracking
    - Dashboard customization
"""

# Log module initialization
logger.info(f"Dashboard module loaded (version {__version__})")

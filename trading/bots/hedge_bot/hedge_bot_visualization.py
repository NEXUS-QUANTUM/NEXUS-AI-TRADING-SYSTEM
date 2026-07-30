# trading/bots/hedge_bot/hedge_bot_visualization.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Visualization Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Visualization Module

This module provides comprehensive data visualization capabilities for the
NEXUS Hedge Bot system. It includes charting, dashboard generation, and
real-time visualization tools.

The module covers:
- Candlestick Charts
- Line Charts
- Bar Charts
- Area Charts
- Heatmaps
- Correlation Matrices
- Equity Curves
- Drawdown Charts
- Performance Dashboards
- Real-time Updates
- Interactive Charts
- Export Capabilities
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

# Try to import optional dependencies
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    from matplotlib.gridspec import GridSpec
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

logger = logging.getLogger(__name__)


# ============================================================
# VISUALIZATION DATACLASSES
# ============================================================

@dataclass
class ChartConfig:
    """Chart configuration"""
    title: str
    width: int = 800
    height: int = 500
    theme: str = "dark"  # dark, light
    template: str = "plotly_dark"
    show_legend: bool = True
    show_grid: bool = True
    interactive: bool = True
    exportable: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "width": self.width,
            "height": self.height,
            "theme": self.theme,
            "template": self.template,
            "show_legend": self.show_legend,
            "show_grid": self.show_grid,
            "interactive": self.interactive,
            "exportable": self.exportable,
        }


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    title: str
    layout: str = "grid"  # grid, vertical, horizontal
    rows: int = 2
    cols: int = 2
    theme: str = "dark"
    refresh_interval: int = 5
    widgets: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "layout": self.layout,
            "rows": self.rows,
            "cols": self.cols,
            "theme": self.theme,
            "refresh_interval": self.refresh_interval,
            "widgets": self.widgets,
        }


# ============================================================
# VISUALIZATION ENGINE
# ============================================================

class VisualizationEngine:
    """
    Comprehensive visualization engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the visualization engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_theme = self.config.get("theme", "dark")
        self.output_dir = Path(self.config.get("output_dir", "charts"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.charts = {}
        self.dashboards = {}
        
        logger.info("Visualization engine initialized")
    
    # ============================================================
    # PLOTLY CHARTS
    # ============================================================
    
    def create_candlestick_chart(
        self,
        data: pd.DataFrame,
        symbol: str,
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a candlestick chart
        
        Args:
            data: OHLCV data
            symbol: Asset symbol
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=f"{symbol} Price Chart")
        
        fig = go.Figure(data=[
            go.Candlestick(
                x=data.index,
                open=data['open'],
                high=data['high'],
                low=data['low'],
                close=data['close'],
                name='OHLC',
            )
        ])
        
        fig.update_layout(
            title=config.title,
            xaxis_title='Date',
            yaxis_title='Price',
            template=config.template,
            height=config.height,
            width=config.width,
            showlegend=config.show_legend,
        )
        
        # Add volume
        if 'volume' in data.columns:
            fig.add_trace(go.Bar(
                x=data.index,
                y=data['volume'],
                name='Volume',
                yaxis='y2',
                marker_color='rgba(0, 212, 255, 0.3)',
            ))
            
            fig.update_layout(
                yaxis2=dict(
                    title='Volume',
                    overlaying='y',
                    side='right',
                    showgrid=False,
                )
            )
        
        # Add moving averages
        if len(data) > 20:
            ma20 = data['close'].rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=data.index,
                y=ma20,
                name='MA 20',
                line=dict(color='orange', width=1),
            ))
        
        if len(data) > 50:
            ma50 = data['close'].rolling(50).mean()
            fig.add_trace(go.Scatter(
                x=data.index,
                y=ma50,
                name='MA 50',
                line=dict(color='green', width=1),
            ))
        
        return fig
    
    def create_line_chart(
        self,
        data: Dict[str, List[float]],
        title: str,
        x_labels: Optional[List[str]] = None,
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a line chart
        
        Args:
            data: Series data
            title: Chart title
            x_labels: X-axis labels
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=title)
        
        fig = go.Figure()
        
        for name, values in data.items():
            fig.add_trace(go.Scatter(
                y=values,
                x=x_labels,
                name=name,
                mode='lines',
            ))
        
        fig.update_layout(
            title=config.title,
            xaxis_title='Date',
            yaxis_title='Value',
            template=config.template,
            height=config.height,
            width=config.width,
            showlegend=config.show_legend,
        )
        
        return fig
    
    def create_bar_chart(
        self,
        data: Dict[str, List[float]],
        title: str,
        x_labels: Optional[List[str]] = None,
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a bar chart
        
        Args:
            data: Series data
            title: Chart title
            x_labels: X-axis labels
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=title)
        
        fig = go.Figure()
        
        for name, values in data.items():
            fig.add_trace(go.Bar(
                y=values,
                x=x_labels,
                name=name,
            ))
        
        fig.update_layout(
            title=config.title,
            xaxis_title='Category',
            yaxis_title='Value',
            template=config.template,
            height=config.height,
            width=config.width,
            barmode='group',
            showlegend=config.show_legend,
        )
        
        return fig
    
    def create_heatmap(
        self,
        data: np.ndarray,
        labels: List[str],
        title: str,
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a heatmap
        
        Args:
            data: Matrix data
            labels: Row/column labels
            title: Chart title
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=title)
        
        fig = go.Figure(data=go.Heatmap(
            z=data,
            x=labels,
            y=labels,
            colorscale='RdBu',
            zmid=0,
        ))
        
        fig.update_layout(
            title=config.title,
            template=config.template,
            height=config.height,
            width=config.width,
        )
        
        return fig
    
    def create_equity_curve(
        self,
        dates: List[datetime],
        equity: List[float],
        benchmark: Optional[List[float]] = None,
        title: str = "Equity Curve",
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create an equity curve chart
        
        Args:
            dates: Date series
            equity: Equity values
            benchmark: Benchmark values
            title: Chart title
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=title)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=equity,
            name='Portfolio',
            mode='lines',
            line=dict(color='#00d4ff', width=2),
        ))
        
        if benchmark:
            fig.add_trace(go.Scatter(
                x=dates,
                y=benchmark,
                name='Benchmark',
                mode='lines',
                line=dict(color='#ff6b6b', width=2, dash='dash'),
            ))
        
        fig.update_layout(
            title=config.title,
            xaxis_title='Date',
            yaxis_title='Value',
            template=config.template,
            height=config.height,
            width=config.width,
            showlegend=config.show_legend,
        )
        
        return fig
    
    def create_drawdown_chart(
        self,
        dates: List[datetime],
        drawdowns: List[float],
        title: str = "Drawdown Chart",
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a drawdown chart
        
        Args:
            dates: Date series
            drawdowns: Drawdown values
            title: Chart title
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=title)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=drawdowns,
            name='Drawdown',
            mode='lines',
            fill='tozeroy',
            line=dict(color='#ff4444', width=2),
            fillcolor='rgba(255,68,68,0.3)',
        ))
        
        fig.update_layout(
            title=config.title,
            xaxis_title='Date',
            yaxis_title='Drawdown (%)',
            template=config.template,
            height=config.height,
            width=config.width,
            showlegend=config.show_legend,
            yaxis=dict(tickformat='.1%'),
        )
        
        return fig
    
    def create_correlation_matrix(
        self,
        returns: pd.DataFrame,
        title: str = "Correlation Matrix",
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a correlation matrix chart
        
        Args:
            returns: Returns data
            title: Chart title
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=title)
        
        corr = returns.corr()
        
        fig = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.columns,
            colorscale='RdBu',
            zmid=0,
            text=corr.values.round(2),
            texttemplate='%{text}',
            textfont={"size": 10},
        ))
        
        fig.update_layout(
            title=config.title,
            template=config.template,
            height=config.height,
            width=config.width,
        )
        
        return fig
    
    # ============================================================
    # DASHBOARD CREATION
    # ============================================================
    
    def create_dashboard(
        self,
        config: DashboardConfig,
        data: Dict[str, Any]
    ) -> Optional[go.Figure]:
        """
        Create a dashboard with multiple charts
        
        Args:
            config: Dashboard configuration
            data: Dashboard data
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        rows = config.rows
        cols = config.cols
        specs = [[{"type": "xy"} for _ in range(cols)] for _ in range(rows)]
        
        fig = make_subplots(
            rows=rows,
            cols=cols,
            specs=specs,
            subplot_titles=[f"Chart {i+1}" for i in range(rows * cols)],
        )
        
        # Add widgets to dashboard
        for i, widget in enumerate(config.widgets[:rows * cols]):
            row = i // cols + 1
            col = i % cols + 1
            
            widget_type = widget.get("type", "line")
            widget_data = widget.get("data", {})
            
            if widget_type == "candlestick":
                df = pd.DataFrame(widget_data)
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name=widget.get("name", "OHLC"),
                ), row=row, col=col)
            
            elif widget_type == "line":
                for name, values in widget_data.items():
                    fig.add_trace(go.Scatter(
                        y=values,
                        name=name,
                        mode='lines',
                    ), row=row, col=col)
            
            elif widget_type == "bar":
                for name, values in widget_data.items():
                    fig.add_trace(go.Bar(
                        y=values,
                        name=name,
                    ), row=row, col=col)
            
            elif widget_type == "heatmap":
                data_matrix = np.array(widget_data.get("data", []))
                labels = widget_data.get("labels", [])
                fig.add_trace(go.Heatmap(
                    z=data_matrix,
                    x=labels,
                    y=labels,
                    colorscale='RdBu',
                ), row=row, col=col)
        
        fig.update_layout(
            title=config.title,
            template='plotly_dark' if config.theme == 'dark' else 'plotly_white',
            height=400 * rows,
            width=600 * cols,
            showlegend=True,
        )
        
        return fig
    
    # ============================================================
    # EXPORT FUNCTIONS
    # ============================================================
    
    def export_chart(
        self,
        fig: Any,
        filename: str,
        format: str = "html"
    ) -> bool:
        """
        Export a chart to file
        
        Args:
            fig: Figure object
            filename: File name
            format: Export format (html, png, jpg, svg)
            
        Returns:
            True if exported
        """
        try:
            filepath = self.output_dir / f"{filename}.{format}"
            
            if format == "html":
                fig.write_html(str(filepath))
            elif format == "png":
                fig.write_image(str(filepath))
            elif format == "jpg":
                fig.write_image(str(filepath))
            elif format == "svg":
                fig.write_image(str(filepath))
            else:
                logger.warning(f"Unsupported format: {format}")
                return False
            
            logger.info(f"Chart exported: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export chart: {e}")
            return False
    
    # ============================================================
    # REAL-TIME VISUALIZATION
    # ============================================================
    
    def create_realtime_chart(
        self,
        symbol: str,
        data: pd.DataFrame,
        update_interval: int = 1,
        config: Optional[ChartConfig] = None
    ) -> Optional[go.Figure]:
        """
        Create a real-time updating chart
        
        Args:
            symbol: Asset symbol
            data: Initial data
            update_interval: Update interval in seconds
            config: Chart configuration
            
        Returns:
            Plotly figure
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed")
            return None
        
        if config is None:
            config = ChartConfig(title=f"{symbol} Real-time Chart")
        
        fig = self.create_candlestick_chart(data, symbol, config)
        
        if fig:
            # Add real-time update capability
            fig.update_layout(
                updatemenus=[dict(
                    type="buttons",
                    buttons=[dict(
                        label="Play",
                        method="animate",
                        args=[None, {"frame": {"duration": 1000 * update_interval, "redraw": True},
                                      "fromcurrent": True}]
                    )]
                )]
            )
        
        return fig
    
    # ============================================================
    # MATPLOTLIB CHARTS (Fallback)
    # ============================================================
    
    def create_matplotlib_chart(
        self,
        data: Dict[str, Any],
        chart_type: str = "line",
        title: str = "Chart",
        figsize: Tuple[int, int] = (12, 6)
    ) -> Optional[Figure]:
        """
        Create a chart using Matplotlib
        
        Args:
            data: Chart data
            chart_type: Chart type
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        if not HAS_MATPLOTLIB:
            logger.warning("Matplotlib not installed")
            return None
        
        fig, ax = plt.subplots(figsize=figsize)
        
        if chart_type == "line":
            for name, values in data.items():
                ax.plot(values, label=name)
        
        elif chart_type == "bar":
            for name, values in data.items():
                ax.bar(range(len(values)), values, label=name)
        
        elif chart_type == "candlestick":
            # Simplified candlestick using matplotlib
            ohlc = data.get("ohlc", [])
            for candle in ohlc:
                color = 'green' if candle['close'] >= candle['open'] else 'red'
                ax.vlines(candle['index'], candle['low'], candle['high'], color=color, linewidth=1)
                ax.vlines(candle['index'], candle['open'], candle['close'], color=color, linewidth=4)
        
        ax.set_title(title)
        ax.legend()
        ax.grid(True)
        
        return fig


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Dataclasses
    "ChartConfig",
    "DashboardConfig",
    
    # Classes
    "VisualizationEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

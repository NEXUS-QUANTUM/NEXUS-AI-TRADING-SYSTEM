# trading/bots/hedge_bot/hedge_bot_data_visualized.py

import asyncio
import logging
import time
import json
import base64
import io
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.io as pio
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class VisualizedChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    CANDLESTICK = "candlestick"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    PIE = "pie"
    DONUT = "donut"
    AREA = "area"
    BOX = "box"
    VIOLIN = "violin"
    WATERFALL = "waterfall"
    FAN = "fan"
    GANTT = "gantt"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    PARALLEL = "parallel"
    RADAR = "radar"
    POLAR = "polar"
    SANKEY = "sankey"
    WORD_CLOUD = "word_cloud"
    CANDLESTICK_OHLC = "candlestick_ohlc"
    HORIZONTAL_BAR = "horizontal_bar"
    STACKED_BAR = "stacked_bar"
    GROUPED_BAR = "grouped_bar"
    FILLED_AREA = "filled_area"
    STEP_LINE = "step_line"


class VisualizedTheme(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    PURPLE = "purple"
    ORANGE = "orange"
    CYBER = "cyber"
    NEXUS = "nexus"
    CORPORATE = "corporate"
    MODERN = "modern"
    RETRO = "retro"
    MONOCHROME = "monochrome"


class VisualizedDataType(str, Enum):
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADING = "trading"
    PORTFOLIO = "portfolio"
    METRICS = "metrics"
    MARKET = "market"
    SENTIMENT = "sentiment"
    CORRELATION = "correlation"
    DISTRIBUTION = "distribution"
    TIMESERIES = "timeseries"


@dataclass
class VisualizedChart:
    id: str
    name: str
    chart_type: VisualizedChartType
    data_type: VisualizedDataType
    theme: VisualizedTheme
    data: Dict[str, Any]
    layout: Dict[str, Any]
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    width: int = 800
    height: int = 400
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None


@dataclass
class VisualizedDashboard:
    id: str
    name: str
    description: str
    charts: List[VisualizedChart]
    layout: Dict[str, Any]
    refresh_interval: float = 60.0
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisualizedReport:
    id: str
    name: str
    description: str
    charts: List[VisualizedChart]
    summary: Dict[str, Any]
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataVisualizedManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._charts: Dict[str, VisualizedChart] = {}
        self._dashboards: Dict[str, VisualizedDashboard] = {}
        self._reports: Dict[str, VisualizedReport] = {}
        self._themes: Dict[VisualizedTheme, Dict[str, Any]] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_themes()

    def _initialize_themes(self) -> None:
        self._themes[VisualizedTheme.LIGHT] = {
            "template": "plotly_white",
            "background": "#ffffff",
            "text": "#333333",
            "grid": "#e5e5e5",
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#ffffff",
            "font_family": "Arial, sans-serif",
            "colors": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
        }
        
        self._themes[VisualizedTheme.DARK] = {
            "template": "plotly_dark",
            "background": "#1a1a2e",
            "text": "#ffffff",
            "grid": "#2d2d44",
            "paper_bgcolor": "#1a1a2e",
            "plot_bgcolor": "#1a1a2e",
            "font_family": "Arial, sans-serif",
            "colors": ["#00d4ff", "#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#a29bfe", "#fd79a8", "#00b894", "#fdcb6e", "#e17055"]
        }
        
        self._themes[VisualizedTheme.NEXUS] = {
            "template": "plotly_dark",
            "background": "#0a0a1a",
            "text": "#00d4ff",
            "grid": "#1a1a3a",
            "paper_bgcolor": "#0a0a1a",
            "plot_bgcolor": "#0a0a1a",
            "font_family": "'Courier New', monospace",
            "colors": ["#00d4ff", "#ff6b6b", "#ffd93d", "#6bcb77", "#a29bfe", "#fd79a8", "#00b894", "#fdcb6e", "#e17055", "#74b9ff"]
        }
        
        self._themes[VisualizedTheme.CYBER] = {
            "template": "plotly_dark",
            "background": "#0d0d0d",
            "text": "#00ff41",
            "grid": "#1a1a1a",
            "paper_bgcolor": "#0d0d0d",
            "plot_bgcolor": "#0d0d0d",
            "font_family": "'Courier New', monospace",
            "colors": ["#00ff41", "#ff00ff", "#00ffff", "#ffff00", "#ff4444", "#44ff44", "#4444ff", "#ff44ff", "#44ffff", "#ffff44"]
        }
        
        self._themes[VisualizedTheme.CORPORATE] = {
            "template": "plotly_white",
            "background": "#f8f9fa",
            "text": "#2c3e50",
            "grid": "#dee2e6",
            "paper_bgcolor": "#f8f9fa",
            "plot_bgcolor": "#f8f9fa",
            "font_family": "'Segoe UI', Arial, sans-serif",
            "colors": ["#2c3e50", "#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c", "#34495e"]
        }

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_chart(
        self,
        name: str,
        chart_type: VisualizedChartType,
        data_type: VisualizedDataType,
        data: Dict[str, Any],
        theme: VisualizedTheme = VisualizedTheme.LIGHT,
        title: Optional[str] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        width: int = 800,
        height: int = 400,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VisualizedChart:
        async with self._lock:
            chart_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            chart = VisualizedChart(
                id=chart_id,
                name=name,
                chart_type=chart_type,
                data_type=data_type,
                theme=theme,
                data=data,
                layout={},
                created_at=time.time(),
                metadata=metadata or {},
                width=width,
                height=height,
                title=title,
                x_label=x_label,
                y_label=y_label
            )
            
            self._charts[chart_id] = chart
            await self._notify_observers("chart_created", chart)
            return chart

    async def render_chart(
        self,
        chart_id: str,
        format: str = "html"
    ) -> Optional[Union[str, bytes]]:
        if chart_id not in self._charts:
            return None
        
        chart = self._charts[chart_id]
        
        if not PLOTLY_AVAILABLE:
            return None
        
        fig = await self._create_plotly_figure(chart)
        
        if format == "html":
            return fig.to_html()
        elif format == "json":
            return fig.to_json()
        elif format == "png":
            return fig.to_image(format="png")
        elif format == "svg":
            return fig.to_image(format="svg")
        elif format == "jpeg":
            return fig.to_image(format="jpeg")
        elif format == "base64":
            img_bytes = fig.to_image(format="png")
            return base64.b64encode(img_bytes).decode()
        else:
            return fig.to_html()

    async def render_matplotlib_chart(
        self,
        chart_id: str,
        format: str = "png",
        dpi: int = 100
    ) -> Optional[bytes]:
        if chart_id not in self._charts:
            return None
        
        chart = self._charts[chart_id]
        
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        fig = await self._create_matplotlib_figure(chart)
        
        buffer = io.BytesIO()
        fig.savefig(buffer, format=format, dpi=dpi, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return buffer.getvalue()

    async def _create_plotly_figure(self, chart: VisualizedChart) -> go.Figure:
        theme_config = self._themes.get(chart.theme, self._themes[VisualizedTheme.LIGHT])
        
        if chart.chart_type == VisualizedChartType.LINE:
            fig = await self._create_line_figure(chart)
        elif chart.chart_type == VisualizedChartType.BAR:
            fig = await self._create_bar_figure(chart)
        elif chart.chart_type == VisualizedChartType.SCATTER:
            fig = await self._create_scatter_figure(chart)
        elif chart.chart_type == VisualizedChartType.CANDLESTICK:
            fig = await self._create_candlestick_figure(chart)
        elif chart.chart_type == VisualizedChartType.HEATMAP:
            fig = await self._create_heatmap_figure(chart)
        elif chart.chart_type == VisualizedChartType.HISTOGRAM:
            fig = await self._create_histogram_figure(chart)
        elif chart.chart_type == VisualizedChartType.PIE:
            fig = await self._create_pie_figure(chart)
        elif chart.chart_type == VisualizedChartType.DONUT:
            fig = await self._create_donut_figure(chart)
        elif chart.chart_type == VisualizedChartType.AREA:
            fig = await self._create_area_figure(chart)
        elif chart.chart_type == VisualizedChartType.BOX:
            fig = await self._create_box_figure(chart)
        elif chart.chart_type == VisualizedChartType.VIOLIN:
            fig = await self._create_violin_figure(chart)
        elif chart.chart_type == VisualizedChartType.TREEMAP:
            fig = await self._create_treemap_figure(chart)
        elif chart.chart_type == VisualizedChartType.SUNBURST:
            fig = await self._create_sunburst_figure(chart)
        elif chart.chart_type == VisualizedChartType.RADAR:
            fig = await self._create_radar_figure(chart)
        elif chart.chart_type == VisualizedChartType.SANKEY:
            fig = await self._create_sankey_figure(chart)
        elif chart.chart_type == VisualizedChartType.CANDLESTICK_OHLC:
            fig = await self._create_candlestick_ohlc_figure(chart)
        elif chart.chart_type == VisualizedChartType.HORIZONTAL_BAR:
            fig = await self._create_horizontal_bar_figure(chart)
        elif chart.chart_type == VisualizedChartType.STACKED_BAR:
            fig = await self._create_stacked_bar_figure(chart)
        elif chart.chart_type == VisualizedChartType.GROUPED_BAR:
            fig = await self._create_grouped_bar_figure(chart)
        elif chart.chart_type == VisualizedChartType.FILLED_AREA:
            fig = await self._create_filled_area_figure(chart)
        elif chart.chart_type == VisualizedChartType.STEP_LINE:
            fig = await self._create_step_line_figure(chart)
        else:
            fig = go.Figure()
        
        fig.update_layout(
            template=theme_config["template"],
            paper_bgcolor=theme_config["paper_bgcolor"],
            plot_bgcolor=theme_config["plot_bgcolor"],
            font_color=theme_config["text"],
            font_family=theme_config.get("font_family", "Arial, sans-serif"),
            width=chart.width,
            height=chart.height,
            title=chart.title,
            xaxis_title=chart.x_label,
            yaxis_title=chart.y_label,
            showlegend=True,
            legend=dict(
                bgcolor=theme_config["paper_bgcolor"],
                bordercolor=theme_config["grid"],
                borderwidth=1
            )
        )
        
        return fig

    async def _create_line_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for col in df.columns:
            if col != x_col:
                fig.add_trace(go.Scatter(
                    x=df[x_col],
                    y=df[col],
                    name=col,
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=6)
                ))
        
        return fig

    async def _create_bar_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for col in df.columns:
            if col != x_col:
                fig.add_trace(go.Bar(
                    x=df[x_col],
                    y=df[col],
                    name=col
                ))
        
        return fig

    async def _create_scatter_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        if 'x' in df.columns and 'y' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['x'],
                y=df['y'],
                mode='markers',
                marker=dict(
                    size=df.get('size', 10),
                    color=df.get('color', None),
                    colorscale='Viridis',
                    showscale=True
                ),
                text=df.get('text', None),
                hoverinfo='text+x+y'
            ))
        
        return fig

    async def _create_candlestick_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.get('date', df.index),
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            increasing_line_color='#00b894',
            decreasing_line_color='#ff6b6b'
        )])
        
        return fig

    async def _create_candlestick_ohlc_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=[go.Ohlc(
            x=df.get('date', df.index),
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close']
        )])
        
        return fig

    async def _create_heatmap_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=go.Heatmap(
            z=df.values,
            x=df.columns,
            y=df.index,
            colorscale='Viridis',
            colorbar=dict(title="Value")
        ))
        
        return fig

    async def _create_histogram_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        for col in df.columns:
            fig.add_trace(go.Histogram(
                x=df[col],
                name=col,
                nbinsx=30,
                opacity=0.7
            ))
        
        fig.update_layout(barmode='overlay')
        return fig

    async def _create_pie_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        labels = df.get('labels', df.index)
        values = df.get('values', df[df.columns[0]])
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.0,
            textinfo='label+percent',
            insidetextorientation='radial'
        )])
        
        return fig

    async def _create_donut_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        labels = df.get('labels', df.index)
        values = df.get('values', df[df.columns[0]])
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            textinfo='label+percent',
            insidetextorientation='radial'
        )])
        
        return fig

    async def _create_area_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for col in df.columns:
            if col != x_col:
                fig.add_trace(go.Scatter(
                    x=df[x_col],
                    y=df[col],
                    name=col,
                    fill='tozeroy',
                    mode='lines'
                ))
        
        return fig

    async def _create_filled_area_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for i, col in enumerate(df.columns):
            if col != x_col:
                fig.add_trace(go.Scatter(
                    x=df[x_col],
                    y=df[col],
                    name=col,
                    fill='tonexty' if i > 0 else 'tozeroy',
                    mode='lines',
                    line=dict(width=1)
                ))
        
        return fig

    async def _create_box_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        for col in df.columns:
            fig.add_trace(go.Box(
                y=df[col],
                name=col,
                boxmean=True,
                boxpoints='outliers'
            ))
        
        return fig

    async def _create_violin_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        for col in df.columns:
            fig.add_trace(go.Violin(
                y=df[col],
                name=col,
                box_visible=True,
                meanline_visible=True,
                points='all'
            ))
        
        return fig

    async def _create_treemap_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(go.Treemap(
            labels=df.get('labels', df.index),
            parents=df.get('parents', ['']),
            values=df.get('values', df[df.columns[0]]),
            textinfo="label+value+percent",
            marker=dict(colors=df.get('colors', None))
        ))
        
        return fig

    async def _create_sunburst_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(go.Sunburst(
            labels=df.get('labels', df.index),
            parents=df.get('parents', ['']),
            values=df.get('values', df[df.columns[0]]),
            textinfo="label+value+percent",
            marker=dict(colors=df.get('colors', None))
        ))
        
        return fig

    async def _create_radar_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        categories = df.get('categories', df.index)
        
        for col in df.columns:
            if col not in ['categories']:
                fig.add_trace(go.Scatterpolar(
                    r=df[col],
                    theta=categories,
                    name=col,
                    fill='toself',
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, df[df.columns[0]].max() * 1.1]
                )
            )
        )
        
        return fig

    async def _create_sankey_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                label=df.get('labels', []),
                color=df.get('colors', 'rgba(0,0,0,0.5)'),
                thickness=20,
                line=dict(color='black', width=0.5)
            ),
            link=dict(
                source=df.get('source', []),
                target=df.get('target', []),
                value=df.get('value', []),
                color=df.get('link_colors', 'rgba(0,0,0,0.2)')
            )
        )])
        
        return fig

    async def _create_horizontal_bar_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        y_col = df.columns[0] if len(df.columns) > 0 else 'y'
        for col in df.columns:
            if col != y_col:
                fig.add_trace(go.Bar(
                    y=df[y_col],
                    x=df[col],
                    name=col,
                    orientation='h'
                ))
        
        return fig

    async def _create_stacked_bar_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for col in df.columns:
            if col != x_col:
                fig.add_trace(go.Bar(
                    x=df[x_col],
                    y=df[col],
                    name=col
                ))
        
        fig.update_layout(barmode='stack')
        return fig

    async def _create_grouped_bar_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for col in df.columns:
            if col != x_col:
                fig.add_trace(go.Bar(
                    x=df[x_col],
                    y=df[col],
                    name=col
                ))
        
        fig.update_layout(barmode='group')
        return fig

    async def _create_step_line_figure(self, chart: VisualizedChart) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        x_col = df.columns[0] if len(df.columns) > 0 else 'x'
        for col in df.columns:
            if col != x_col:
                fig.add_trace(go.Scatter(
                    x=df[x_col],
                    y=df[col],
                    name=col,
                    line_shape='hv',
                    mode='lines'
                ))
        
        return fig

    async def _create_matplotlib_figure(self, chart: VisualizedChart) -> Figure:
        fig, ax = plt.subplots(figsize=(chart.width/100, chart.height/100))
        
        df = pd.DataFrame(chart.data)
        
        if chart.chart_type == VisualizedChartType.LINE:
            for col in df.columns:
                if col != df.columns[0]:
                    ax.plot(df[df.columns[0]], df[col], label=col, marker='o')
        
        elif chart.chart_type == VisualizedChartType.BAR:
            x = df[df.columns[0]] if len(df.columns) > 0 else df.index
            for col in df.columns:
                if col != df.columns[0]:
                    ax.bar(x, df[col], label=col, alpha=0.7)
        
        elif chart.chart_type == VisualizedChartType.SCATTER:
            if 'x' in df.columns and 'y' in df.columns:
                ax.scatter(df['x'], df['y'], s=df.get('size', 30), c=df.get('color', 'blue'))
        
        elif chart.chart_type == VisualizedChartType.PIE:
            labels = df.get('labels', df.index)
            values = df.get('values', df[df.columns[0]])
            ax.pie(values, labels=labels, autopct='%1.1f%%')
        
        elif chart.chart_type == VisualizedChartType.HISTOGRAM:
            for col in df.columns:
                ax.hist(df[col], bins=30, alpha=0.7, label=col)
        
        elif chart.chart_type == VisualizedChartType.BOX:
            ax.boxplot([df[col] for col in df.columns], labels=df.columns)
        
        else:
            for col in df.columns:
                if col != df.columns[0]:
                    ax.plot(df[df.columns[0]], df[col], label=col)
        
        if chart.title:
            ax.set_title(chart.title)
        if chart.x_label:
            ax.set_xlabel(chart.x_label)
        if chart.y_label:
            ax.set_ylabel(chart.y_label)
        
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        theme_config = self._themes.get(chart.theme, self._themes[VisualizedTheme.LIGHT])
        fig.patch.set_facecolor(theme_config["background"])
        ax.set_facecolor(theme_config["background"])
        ax.spines['top'].set_color(theme_config["grid"])
        ax.spines['bottom'].set_color(theme_config["grid"])
        ax.spines['left'].set_color(theme_config["grid"])
        ax.spines['right'].set_color(theme_config["grid"])
        ax.tick_params(colors=theme_config["text"])
        ax.xaxis.label.set_color(theme_config["text"])
        ax.yaxis.label.set_color(theme_config["text"])
        ax.title.set_color(theme_config["text"])
        
        return fig

    async def create_dashboard(
        self,
        name: str,
        description: str,
        chart_ids: List[str],
        layout: Optional[Dict[str, Any]] = None,
        refresh_interval: float = 60.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VisualizedDashboard:
        async with self._lock:
            dashboard_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            charts = []
            for chart_id in chart_ids:
                if chart_id in self._charts:
                    charts.append(self._charts[chart_id])
            
            dashboard = VisualizedDashboard(
                id=dashboard_id,
                name=name,
                description=description,
                charts=charts,
                layout=layout or {"rows": 2, "cols": 2},
                refresh_interval=refresh_interval,
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._dashboards[dashboard_id] = dashboard
            await self._notify_observers("dashboard_created", dashboard)
            return dashboard

    async def create_report(
        self,
        name: str,
        description: str,
        chart_ids: List[str],
        summary: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> VisualizedReport:
        async with self._lock:
            report_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            charts = []
            for chart_id in chart_ids:
                if chart_id in self._charts:
                    charts.append(self._charts[chart_id])
            
            report = VisualizedReport(
                id=report_id,
                name=name,
                description=description,
                charts=charts,
                summary=summary,
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._reports[report_id] = report
            await self._notify_observers("report_created", report)
            return report

    async def get_chart(self, chart_id: str) -> Optional[VisualizedChart]:
        return self._charts.get(chart_id)

    async def get_charts(self) -> List[VisualizedChart]:
        return list(self._charts.values())

    async def get_dashboard(self, dashboard_id: str) -> Optional[VisualizedDashboard]:
        return self._dashboards.get(dashboard_id)

    async def get_dashboards(self) -> List[VisualizedDashboard]:
        return list(self._dashboards.values())

    async def get_report(self, report_id: str) -> Optional[VisualizedReport]:
        return self._reports.get(report_id)

    async def get_reports(self) -> List[VisualizedReport]:
        return list(self._reports.values())

    async def delete_chart(self, chart_id: str) -> bool:
        if chart_id in self._charts:
            del self._charts[chart_id]
            return True
        return False

    async def delete_dashboard(self, dashboard_id: str) -> bool:
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            return True
        return False

    async def delete_report(self, report_id: str) -> bool:
        if report_id in self._reports:
            del self._reports[report_id]
            return True
        return False

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "charts": len(self._charts),
            "dashboards": len(self._dashboards),
            "reports": len(self._reports),
            "themes": len(self._themes),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "VisualizedChartType",
    "VisualizedTheme",
    "VisualizedDataType",
    "VisualizedChart",
    "VisualizedDashboard",
    "VisualizedReport",
    "DataVisualizedManager"
]

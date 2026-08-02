# trading/bots/hedge_bot/hedge_bot_data_visualization.py

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


class ChartType(str, Enum):
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


class ChartTheme(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    PURPLE = "purple"
    ORANGE = "orange"
    CYBER = "cyber"
    NEXUS = "nexus"


class VisualizationType(str, Enum):
    STATIC = "static"
    INTERACTIVE = "interactive"
    ANIMATED = "animated"
    DASHBOARD = "dashboard"


@dataclass
class ChartData:
    id: str
    name: str
    type: ChartType
    data: Any
    layout: Dict[str, Any]
    theme: ChartTheme
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChartConfig:
    id: str
    name: str
    chart_type: ChartType
    theme: ChartTheme = ChartTheme.LIGHT
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    width: int = 800
    height: int = 400
    colors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Dashboard:
    id: str
    name: str
    description: str
    charts: List[ChartData]
    layout: Dict[str, Any]
    refresh_interval: float = 60.0
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataVisualizationManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._charts: Dict[str, ChartData] = {}
        self._configs: Dict[str, ChartConfig] = {}
        self._dashboards: Dict[str, Dashboard] = {}
        self._themes: Dict[ChartTheme, Dict[str, Any]] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_themes()
        self._initialize_default_configs()

    def _initialize_themes(self) -> None:
        self._themes[ChartTheme.LIGHT] = {
            "template": "plotly_white",
            "background": "#ffffff",
            "text": "#333333",
            "grid": "#e5e5e5",
            "colors": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
        }
        
        self._themes[ChartTheme.DARK] = {
            "template": "plotly_dark",
            "background": "#1a1a2e",
            "text": "#ffffff",
            "grid": "#2d2d44",
            "colors": ["#00d4ff", "#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#ff6b6b", "#a29bfe", "#fd79a8", "#00b894", "#fdcb6e"]
        }
        
        self._themes[ChartTheme.NEXUS] = {
            "template": "plotly_dark",
            "background": "#0a0a1a",
            "text": "#00d4ff",
            "grid": "#1a1a3a",
            "colors": ["#00d4ff", "#ff6b6b", "#ffd93d", "#6bcb77", "#a29bfe", "#fd79a8", "#00b894", "#fdcb6e", "#e17055", "#74b9ff"]
        }
        
        self._themes[ChartTheme.CYBER] = {
            "template": "plotly_dark",
            "background": "#0d0d0d",
            "text": "#00ff41",
            "grid": "#1a1a1a",
            "colors": ["#00ff41", "#ff00ff", "#00ffff", "#ffff00", "#ff4444", "#44ff44", "#4444ff", "#ff44ff", "#44ffff", "#ffff44"]
        }

    def _initialize_default_configs(self) -> None:
        default_configs = [
            ChartConfig(
                id="performance_line",
                name="Performance Line Chart",
                chart_type=ChartType.LINE,
                title="Performance Over Time",
                x_label="Date",
                y_label="Value",
                width=800,
                height=400
            ),
            ChartConfig(
                id="pnl_bar",
                name="PnL Bar Chart",
                chart_type=ChartType.BAR,
                title="Profit and Loss",
                x_label="Category",
                y_label="PnL",
                width=800,
                height=400
            ),
            ChartConfig(
                id="risk_heatmap",
                name="Risk Heatmap",
                chart_type=ChartType.HEATMAP,
                title="Risk Matrix",
                width=600,
                height=600
            ),
            ChartConfig(
                id="candlestick",
                name="Candlestick Chart",
                chart_type=ChartType.CANDLESTICK,
                title="Price Action",
                width=800,
                height=500
            ),
            ChartConfig(
                id="distribution_histogram",
                name="Distribution Histogram",
                chart_type=ChartType.HISTOGRAM,
                title="Return Distribution",
                x_label="Return",
                y_label="Frequency",
                width=700,
                height=400
            ),
            ChartConfig(
                id="portfolio_pie",
                name="Portfolio Pie Chart",
                chart_type=ChartType.PIE,
                title="Portfolio Allocation",
                width=500,
                height=500
            )
        ]
        
        for config in default_configs:
            self._configs[config.id] = config

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_chart(
        self,
        config_id: str,
        data: Dict[str, Any],
        theme: ChartTheme = ChartTheme.LIGHT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChartData]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            chart_id = hashlib.md5(f"{config_id}_{time.time()}".encode()).hexdigest()
            
            chart_data = ChartData(
                id=chart_id,
                name=config.name,
                type=config.chart_type,
                data=data,
                layout={},
                theme=theme,
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._charts[chart_id] = chart_data
            await self._notify_observers("chart_created", chart_data)
            return chart_data

    async def render_chart(
        self,
        chart_id: str,
        format: str = "html",
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> Optional[Union[str, bytes]]:
        if chart_id not in self._charts:
            return None
        
        chart = self._charts[chart_id]
        config = self._configs.get(chart.id)
        
        if not config:
            config = self._get_default_config(chart.type)
        
        if not PLOTLY_AVAILABLE:
            return None
        
        fig = await self._create_plotly_figure(chart, config, width, height)
        
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
        else:
            return fig.to_html()

    async def _create_plotly_figure(
        self,
        chart: ChartData,
        config: ChartConfig,
        width: Optional[int],
        height: Optional[int]
    ) -> go.Figure:
        theme_config = self._themes.get(chart.theme, self._themes[ChartTheme.LIGHT])
        
        if chart.type == ChartType.LINE:
            fig = await self._create_line_chart(chart, config)
        elif chart.type == ChartType.BAR:
            fig = await self._create_bar_chart(chart, config)
        elif chart.type == ChartType.SCATTER:
            fig = await self._create_scatter_chart(chart, config)
        elif chart.type == ChartType.CANDLESTICK:
            fig = await self._create_candlestick_chart(chart, config)
        elif chart.type == ChartType.HEATMAP:
            fig = await self._create_heatmap_chart(chart, config)
        elif chart.type == ChartType.HISTOGRAM:
            fig = await self._create_histogram_chart(chart, config)
        elif chart.type == ChartType.PIE:
            fig = await self._create_pie_chart(chart, config)
        elif chart.type == ChartType.DONUT:
            fig = await self._create_donut_chart(chart, config)
        elif chart.type == ChartType.AREA:
            fig = await self._create_area_chart(chart, config)
        elif chart.type == ChartType.BOX:
            fig = await self._create_box_chart(chart, config)
        elif chart.type == ChartType.VIOLIN:
            fig = await self._create_violin_chart(chart, config)
        elif chart.type == ChartType.TREEMAP:
            fig = await self._create_treemap_chart(chart, config)
        elif chart.type == ChartType.SUNBURST:
            fig = await self._create_sunburst_chart(chart, config)
        elif chart.type == ChartType.RADAR:
            fig = await self._create_radar_chart(chart, config)
        elif chart.type == ChartType.SANKEY:
            fig = await self._create_sankey_chart(chart, config)
        else:
            fig = go.Figure()
        
        fig.update_layout(
            template=theme_config["template"],
            paper_bgcolor=theme_config["background"],
            plot_bgcolor=theme_config["background"],
            font_color=theme_config["text"],
            width=width or config.width,
            height=height or config.height,
            title=config.title,
            xaxis_title=config.x_label,
            yaxis_title=config.y_label
        )
        
        return fig

    async def _create_line_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        for col in df.columns:
            if col not in ['x', 'date', 'time']:
                fig.add_trace(go.Scatter(
                    x=df.get('x', df.get('date', df.index)),
                    y=df[col],
                    name=col,
                    mode='lines+markers'
                ))
        
        return fig

    async def _create_bar_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        fig = go.Figure()
        
        for col in df.columns:
            if col not in ['x', 'category', 'label']:
                fig.add_trace(go.Bar(
                    x=df.get('x', df.get('category', df.index)),
                    y=df[col],
                    name=col
                ))
        
        return fig

    async def _create_scatter_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
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
                    colorscale='Viridis'
                )
            ))
        
        return fig

    async def _create_candlestick_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.get('date', df.index),
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close']
        )])
        
        return fig

    async def _create_heatmap_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=go.Heatmap(
            z=df.values,
            x=df.columns,
            y=df.index,
            colorscale='Viridis'
        ))
        
        return fig

    async def _create_histogram_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure()
        
        for col in df.columns:
            fig.add_trace(go.Histogram(
                x=df[col],
                name=col,
                nbinsx=30
            ))
        
        return fig

    async def _create_pie_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        labels = df.get('labels', df.index)
        values = df.get('values', df[df.columns[0]])
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.0
        )])
        
        return fig

    async def _create_donut_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        labels = df.get('labels', df.index)
        values = df.get('values', df[df.columns[0]])
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4
        )])
        
        return fig

    async def _create_area_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure()
        
        for col in df.columns:
            if col not in ['x', 'date']:
                fig.add_trace(go.Scatter(
                    x=df.get('x', df.get('date', df.index)),
                    y=df[col],
                    name=col,
                    fill='tozeroy',
                    mode='lines'
                ))
        
        return fig

    async def _create_box_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure()
        
        for col in df.columns:
            fig.add_trace(go.Box(
                y=df[col],
                name=col
            ))
        
        return fig

    async def _create_violin_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure()
        
        for col in df.columns:
            fig.add_trace(go.Violin(
                y=df[col],
                name=col,
                box_visible=True,
                meanline_visible=True
            ))
        
        return fig

    async def _create_treemap_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(go.Treemap(
            labels=df.get('labels', df.index),
            parents=df.get('parents', ['']),
            values=df.get('values', df[df.columns[0]]),
            textinfo="label+value"
        ))
        
        return fig

    async def _create_sunburst_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(go.Sunburst(
            labels=df.get('labels', df.index),
            parents=df.get('parents', ['']),
            values=df.get('values', df[df.columns[0]]),
            textinfo="label+value"
        ))
        
        return fig

    async def _create_radar_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure()
        
        categories = df.get('categories', df.index)
        
        for col in df.columns:
            if col not in ['categories']:
                fig.add_trace(go.Scatterpolar(
                    r=df[col],
                    theta=categories,
                    name=col,
                    fill='toself'
                ))
        
        fig.update_layout(polar=dict(
            radialaxis=dict(
                visible=True,
                range=df[df.columns[0]].min(), df[df.columns[0]].max()
            )
        ))
        
        return fig

    async def _create_sankey_chart(self, chart: ChartData, config: ChartConfig) -> go.Figure:
        df = pd.DataFrame(chart.data)
        
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                label=df.get('labels', []),
                color=df.get('colors', 'rgba(0,0,0,0.5)')
            ),
            link=dict(
                source=df.get('source', []),
                target=df.get('target', []),
                value=df.get('value', [])
            )
        )])
        
        return fig

    def _get_default_config(self, chart_type: ChartType) -> ChartConfig:
        return ChartConfig(
            id="default",
            name="Default Chart",
            chart_type=chart_type,
            title=str(chart_type.value).capitalize(),
            width=800,
            height=400
        )

    async def create_dashboard(
        self,
        name: str,
        description: str,
        chart_ids: List[str],
        layout: Optional[Dict[str, Any]] = None,
        refresh_interval: float = 60.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dashboard:
        async with self._lock:
            dashboard_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            charts = []
            for chart_id in chart_ids:
                if chart_id in self._charts:
                    charts.append(self._charts[chart_id])
            
            dashboard = Dashboard(
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

    async def render_dashboard(
        self,
        dashboard_id: str,
        format: str = "html"
    ) -> Optional[str]:
        if dashboard_id not in self._dashboards:
            return None
        
        dashboard = self._dashboards[dashboard_id]
        
        if not PLOTLY_AVAILABLE:
            return None
        
        figs = []
        for chart in dashboard.charts:
            config = self._configs.get(chart.id)
            if not config:
                config = self._get_default_config(chart.type)
            
            fig = await self._create_plotly_figure(chart, config, 400, 300)
            figs.append(fig)
        
        if format == "html":
            html = '<!DOCTYPE html><html><head><title>{}</title></head><body>'.format(dashboard.name)
            html += '<h1>{}</h1><p>{}</p>'.format(dashboard.name, dashboard.description)
            html += '<div style="display: grid; grid-template-columns: repeat({}, 1fr); gap: 20px;">'.format(dashboard.layout.get("cols", 2))
            
            for fig in figs:
                html += '<div>{}</div>'.format(fig.to_html(include_plotlyjs='cdn'))
            
            html += '</div></body></html>'
            return html
        
        return None

    async def get_chart(self, chart_id: str) -> Optional[ChartData]:
        return self._charts.get(chart_id)

    async def get_charts(self) -> List[ChartData]:
        return list(self._charts.values())

    async def get_config(self, config_id: str) -> Optional[ChartConfig]:
        return self._configs.get(config_id)

    async def get_configs(self) -> List[ChartConfig]:
        return list(self._configs.values())

    async def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        return self._dashboards.get(dashboard_id)

    async def get_dashboards(self) -> List[Dashboard]:
        return list(self._dashboards.values())

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
            "configs": len(self._configs),
            "dashboards": len(self._dashboards),
            "themes": len(self._themes),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "ChartType",
    "ChartTheme",
    "VisualizationType",
    "ChartData",
    "ChartConfig",
    "Dashboard",
    "DataVisualizationManager"
]

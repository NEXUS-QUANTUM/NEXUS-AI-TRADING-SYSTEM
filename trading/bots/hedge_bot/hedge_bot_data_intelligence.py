# trading/bots/hedge_bot/hedge_bot_data_intelligence.py
# Advanced Business Intelligence & Analytics Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Intelligence Module - Module avancé de business intelligence et d'analytique
pour le Hedge Bot. Fournit des capacités d'analyse avancée, de reporting, de visualisation,
de détection d'anomalies et de prédiction des tendances pour le système de hedging.
"""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import pickle
import zlib
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_intelligence")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult, DecisionType
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult
)


# ============== ENUMS & TYPES ==============

class IntelligenceMetric(Enum):
    """Métriques d'intelligence."""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    MAX_DRAWDOWN = "max_drawdown"
    RECOVERY_FACTOR = "recovery_factor"
    HEDGE_EFFECTIVENESS = "hedge_effectiveness"
    DECISION_ACCURACY = "decision_accuracy"
    EXECUTION_QUALITY = "execution_quality"
    RISK_ADJUSTED_RETURN = "risk_adjusted_return"


class IntelligenceReportType(Enum):
    """Types de rapports d'intelligence."""
    EXECUTIVE = "executive"
    DETAILED = "detailed"
    TECHNICAL = "technical"
    RISK = "risk"
    PERFORMANCE = "performance"
    TRADING = "trading"
    HEDGE = "hedge"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class IntelligenceVisualizationType(Enum):
    """Types de visualisations."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    HEATMAP = "heatmap"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOXPLOT = "boxplot"
    CANDLESTICK = "candlestick"
    GAUGE = "gauge"
    RADAR = "radar"


# ============== DATA MODELS ==============

@dataclass
class IntelligenceMetricValue:
    """Valeur de métrique d'intelligence."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metric: IntelligenceMetric = IntelligenceMetric.SHARPE_RATIO
    value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    threshold: float = 0.0
    status: str = "normal"  # normal, warning, critical, excellent


@dataclass
class IntelligenceReport:
    """Rapport d'intelligence."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    report_type: IntelligenceReportType = IntelligenceReportType.EXECUTIVE
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    metrics: List[IntelligenceMetricValue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    visualizations: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class IntelligenceAnomaly:
    """Anomalie détectée."""
    anomaly_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric: IntelligenceMetric = IntelligenceMetric.SHARPE_RATIO
    value: float = 0.0
    expected: float = 0.0
    deviation: float = 0.0
    severity: str = "low"  # low, medium, high, critical
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_note: Optional[str] = None


# ============== INTERFACES ==============

class IntelligenceEngineInterface(ABC):
    """Interface abstraite pour le moteur d'intelligence."""
    
    @abstractmethod
    async def calculate_metrics(self, data: Dict[str, Any]) -> List[IntelligenceMetricValue]:
        """Calcule les métriques d'intelligence."""
        pass
    
    @abstractmethod
    async def generate_report(self, report_type: IntelligenceReportType) -> IntelligenceReport:
        """Génère un rapport d'intelligence."""
        pass
    
    @abstractmethod
    async def detect_anomalies(self, data: Dict[str, Any]) -> List[IntelligenceAnomaly]:
        """Détecte des anomalies."""
        pass


# ============== IMPLÉMENTATION ==============

class IntelligenceEngine(IntelligenceEngineInterface):
    """
    Moteur d'intelligence avancé pour le Hedge Bot.
    Fournit des capacités d'analyse, de reporting et de détection d'anomalies.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des métriques
        self._metrics: Dict[str, List[IntelligenceMetricValue]] = defaultdict(list)
        self._metrics_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, IntelligenceReport] = {}
        self._reports_lock = threading.RLock()
        
        # Gestion des anomalies
        self._anomalies: List[IntelligenceAnomaly] = []
        self._anomalies_lock = threading.RLock()
        
        # Cache des visualisations
        self._viz_cache: Dict[str, str] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "metrics_calculated": 0,
            "reports_generated": 0,
            "anomalies_detected": 0,
            "anomalies_resolved": 0,
            "viz_generated": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("IntelligenceEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_report_type": IntelligenceReportType.EXECUTIVE,
            "anomaly_threshold": 2.0,
            "anomaly_window": 30,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_caching": True,
            "enable_visualizations": True,
            "report_interval": 86400,
            "max_reports": 100,
            "metric_retention_days": 90,
            "visualization_dpi": 100,
            "chart_style": "darkgrid",
            "color_palette": "husl"
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'intelligence."""
        logger.info("IntelligenceEngine starting...")
        self._is_running = True
        
        # Configuration de matplotlib
        plt.style.use(self.config["chart_style"])
        sns.set_palette(self.config["color_palette"])
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._report_generator_loop())
        asyncio.create_task(self._anomaly_scan_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("IntelligenceEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'intelligence."""
        logger.info("IntelligenceEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des métriques
        await self._save_metrics()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("IntelligenceEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def calculate_metrics(self, data: Dict[str, Any]) -> List[IntelligenceMetricValue]:
        """Calcule les métriques d'intelligence."""
        metrics = []
        
        try:
            # Calcul des métriques de performance
            if "returns" in data:
                returns = np.array(data["returns"])
                
                # Sharpe Ratio
                sharpe = self._calculate_sharpe(returns)
                metrics.append(self._create_metric(
                    IntelligenceMetric.SHARPE_RATIO,
                    sharpe,
                    data.get("risk_free_rate", 0.02)
                ))
                
                # Sortino Ratio
                sortino = self._calculate_sortino(returns)
                metrics.append(self._create_metric(
                    IntelligenceMetric.SORTINO_RATIO,
                    sortino
                ))
                
                # Calmar Ratio
                calmar = self._calculate_calmar(returns)
                metrics.append(self._create_metric(
                    IntelligenceMetric.CALMAR_RATIO,
                    calmar
                ))
                
                # Win Rate
                win_rate = self._calculate_win_rate(returns)
                metrics.append(self._create_metric(
                    IntelligenceMetric.WIN_RATE,
                    win_rate
                ))
            
            # Calcul des métriques de trading
            if "trades" in data:
                trades = data["trades"]
                
                # Profit Factor
                profit_factor = self._calculate_profit_factor(trades)
                metrics.append(self._create_metric(
                    IntelligenceMetric.PROFIT_FACTOR,
                    profit_factor
                ))
                
                # Expected Value
                expected_value = self._calculate_expected_value(trades)
                metrics.append(self._create_metric(
                    IntelligenceMetric.EXPECTED_VALUE,
                    expected_value
                ))
            
            # Calcul des métriques de risque
            if "drawdowns" in data:
                drawdowns = data["drawdowns"]
                max_drawdown = max(drawdowns) if drawdowns else 0
                metrics.append(self._create_metric(
                    IntelligenceMetric.MAX_DRAWDOWN,
                    max_drawdown
                ))
            
            # Stockage des métriques
            with self._metrics_lock:
                for metric in metrics:
                    self._metrics[metric.metric.value].append(metric)
                    self._stats["metrics_calculated"] += 1
            
            return metrics
            
        except Exception as e:
            logger.error(f"Metrics calculation error: {e}")
            return metrics
    
    async def generate_report(
        self,
        report_type: IntelligenceReportType = IntelligenceReportType.EXECUTIVE
    ) -> IntelligenceReport:
        """Génère un rapport d'intelligence."""
        self._stats["reports_generated"] += 1
        
        try:
            # Récupération des métriques récentes
            recent_metrics = await self._get_recent_metrics()
            
            # Calcul des métriques agrégées
            summary = await self._generate_summary(recent_metrics)
            
            # Génération des visualisations
            visualizations = []
            if self.config["enable_visualizations"]:
                visualizations = await self._generate_visualizations(
                    recent_metrics,
                    report_type
                )
            
            # Génération des insights
            insights = await self._generate_insights(recent_metrics)
            
            # Génération des risques
            risks = await self._identify_risks(recent_metrics)
            
            # Génération des recommandations
            recommendations = await self._generate_recommendations(
                recent_metrics,
                insights,
                risks
            )
            
            # Création du rapport
            report = IntelligenceReport(
                name=f"{report_type.value.capitalize()} Report",
                report_type=report_type,
                period_start=datetime.now(timezone.utc) - timedelta(days=30),
                period_end=datetime.now(timezone.utc),
                metrics=recent_metrics,
                summary=summary,
                visualizations=visualizations,
                recommendations=recommendations,
                risks=risks,
                insights=insights,
                metadata={"generated_by": "intelligence_engine"}
            )
            
            # Stockage du rapport
            with self._reports_lock:
                self._reports[report.report_id] = report
                
                # Limitation du nombre de rapports
                if len(self._reports) > self.config["max_reports"]:
                    oldest = min(self._reports.keys())
                    del self._reports[oldest]
            
            logger.info(f"Report generated: {report.name} (id={report.report_id})")
            return report
            
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            raise
    
    async def detect_anomalies(self, data: Dict[str, Any]) -> List[IntelligenceAnomaly]:
        """Détecte des anomalies."""
        anomalies = []
        
        try:
            # Détection des anomalies dans les rendements
            if "returns" in data:
                returns = np.array(data["returns"])
                mean = np.mean(returns)
                std = np.std(returns)
                
                for i, ret in enumerate(returns):
                    z_score = (ret - mean) / std if std > 0 else 0
                    if abs(z_score) > self.config["anomaly_threshold"]:
                        anomaly = IntelligenceAnomaly(
                            metric=IntelligenceMetric.EXPECTED_VALUE,
                            value=ret,
                            expected=mean,
                            deviation=z_score,
                            severity=self._determine_severity(abs(z_score)),
                            context={"index": i, "z_score": z_score}
                        )
                        anomalies.append(anomaly)
            
            # Détection des anomalies dans les drawdowns
            if "drawdowns" in data:
                drawdowns = data["drawdowns"]
                mean_dd = np.mean(drawdowns) if drawdowns else 0
                std_dd = np.std(drawdowns) if drawdowns else 1
                
                for i, dd in enumerate(drawdowns):
                    z_score = (dd - mean_dd) / std_dd if std_dd > 0 else 0
                    if abs(z_score) > self.config["anomaly_threshold"]:
                        anomaly = IntelligenceAnomaly(
                            metric=IntelligenceMetric.MAX_DRAWDOWN,
                            value=dd,
                            expected=mean_dd,
                            deviation=z_score,
                            severity=self._determine_severity(abs(z_score)),
                            context={"index": i, "z_score": z_score}
                        )
                        anomalies.append(anomaly)
            
            # Stockage des anomalies
            with self._anomalies_lock:
                self._anomalies.extend(anomalies)
                self._stats["anomalies_detected"] += len(anomalies)
            
            logger.info(f"Detected {len(anomalies)} anomalies")
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")
            return anomalies
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    def _calculate_sharpe(self, returns: np.ndarray, risk_free: float = 0.02) -> float:
        """Calcule le Sharpe Ratio."""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free / 252
        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns)
        
        return mean_return / std_return * np.sqrt(252) if std_return > 0 else 0
    
    def _calculate_sortino(self, returns: np.ndarray) -> float:
        """Calcule le Sortino Ratio."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        downside = returns[returns < 0]
        downside_std = np.std(downside) if len(downside) > 0 else 0
        
        return mean_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    def _calculate_calmar(self, returns: np.ndarray) -> float:
        """Calcule le Calmar Ratio."""
        if len(returns) < 2:
            return 0.0
        
        annual_return = np.mean(returns) * 252
        cumulative = (1 + returns).cumprod()
        drawdown = (cumulative - cumulative.expanding().max()) / cumulative.expanding().max()
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        return annual_return / max_drawdown if max_drawdown > 0 else 0
    
    def _calculate_win_rate(self, returns: np.ndarray) -> float:
        """Calcule le taux de réussite."""
        if len(returns) == 0:
            return 0.0
        
        wins = np.sum(returns > 0)
        total = len(returns)
        return wins / total if total > 0 else 0
    
    def _calculate_profit_factor(self, trades: List[Dict]) -> float:
        """Calcule le Profit Factor."""
        gross_profit = sum(t.get("profit", 0) for t in trades if t.get("profit", 0) > 0)
        gross_loss = abs(sum(t.get("profit", 0) for t in trades if t.get("profit", 0) < 0))
        
        return gross_profit / gross_loss if gross_loss > 0 else 0
    
    def _calculate_expected_value(self, trades: List[Dict]) -> float:
        """Calcule la valeur espérée."""
        if not trades:
            return 0.0
        
        profits = [t.get("profit", 0) for t in trades]
        return np.mean(profits) if profits else 0
    
    def _create_metric(
        self,
        metric: IntelligenceMetric,
        value: float,
        threshold: float = 0.0
    ) -> IntelligenceMetricValue:
        """Crée une métrique d'intelligence."""
        return IntelligenceMetricValue(
            name=metric.value.replace("_", " ").title(),
            metric=metric,
            value=value,
            threshold=threshold,
            status=self._determine_status(metric, value, threshold)
        )
    
    def _determine_status(
        self,
        metric: IntelligenceMetric,
        value: float,
        threshold: float
    ) -> str:
        """Détermine le statut d'une métrique."""
        if threshold == 0:
            return "normal"
        
        ratio = value / threshold if threshold != 0 else 0
        
        if ratio >= 1.5:
            return "excellent"
        elif ratio >= 1.0:
            return "normal"
        elif ratio >= 0.5:
            return "warning"
        else:
            return "critical"
    
    def _determine_severity(self, z_score: float) -> str:
        """Détermine la sévérité d'une anomalie."""
        if z_score > 5.0:
            return "critical"
        elif z_score > 3.0:
            return "high"
        elif z_score > 2.0:
            return "medium"
        else:
            return "low"
    
    # ========== MÉTHODES PRIVÉES - RAPPORTS ==========
    
    async def _get_recent_metrics(self) -> List[IntelligenceMetricValue]:
        """Récupère les métriques récentes."""
        metrics = []
        with self._metrics_lock:
            for metric_list in self._metrics.values():
                if metric_list:
                    # Dernière métrique de chaque type
                    metrics.append(metric_list[-1])
        return metrics
    
    async def _generate_summary(self, metrics: List[IntelligenceMetricValue]) -> Dict[str, Any]:
        """Génère un résumé des métriques."""
        summary = {
            "total_metrics": len(metrics),
            "status_counts": defaultdict(int),
            "key_metrics": {}
        }
        
        for metric in metrics:
            summary["status_counts"][metric.status] += 1
            
            # Métriques clés
            if metric.metric in [
                IntelligenceMetric.SHARPE_RATIO,
                IntelligenceMetric.WIN_RATE,
                IntelligenceMetric.PROFIT_FACTOR,
                IntelligenceMetric.MAX_DRAWDOWN
            ]:
                summary["key_metrics"][metric.metric.value] = {
                    "value": metric.value,
                    "status": metric.status
                }
        
        # Calcul du score global
        status_scores = {"excellent": 5, "normal": 3, "warning": 2, "critical": 0}
        total_score = sum(status_scores.get(s, 1) for s in summary["status_counts"].keys())
        summary["overall_score"] = total_score / len(metrics) if metrics else 0
        
        return summary
    
    async def _generate_visualizations(
        self,
        metrics: List[IntelligenceMetricValue],
        report_type: IntelligenceReportType
    ) -> List[Dict[str, Any]]:
        """Génère des visualisations."""
        visualizations = []
        
        # Construction du DataFrame
        data = []
        for metric in metrics:
            data.append({
                "metric": metric.metric.value,
                "value": metric.value,
                "status": metric.status,
                "timestamp": metric.timestamp
            })
        df = pd.DataFrame(data)
        
        if df.empty:
            return visualizations
        
        try:
            # 1. Bar chart des métriques
            fig, ax = plt.subplots(figsize=(12, 6))
            colors = {
                "excellent": "#2ecc71",
                "normal": "#3498db",
                "warning": "#f39c12",
                "critical": "#e74c3c"
            }
            df_sorted = df.sort_values("value", ascending=True)
            bars = ax.barh(df_sorted["metric"], df_sorted["value"])
            
            for bar, status in zip(bars, df_sorted["status"]):
                bar.set_color(colors.get(status, "#95a5a6"))
            
            ax.set_title("Intelligence Metrics Overview")
            ax.set_xlabel("Value")
            ax.set_ylabel("Metric")
            
            # Légende
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=colors.get("excellent"), label="Excellent"),
                Patch(facecolor=colors.get("normal"), label="Normal"),
                Patch(facecolor=colors.get("warning"), label="Warning"),
                Patch(facecolor=colors.get("critical"), label="Critical")
            ]
            ax.legend(handles=legend_elements, loc="lower right")
            
            plt.tight_layout()
            
            # Conversion en base64
            buf = BytesIO()
            plt.savefig(buf, format="png", dpi=self.config["visualization_dpi"])
            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode()
            
            visualizations.append({
                "type": IntelligenceVisualizationType.BAR.value,
                "title": "Metrics Overview",
                "data": img_base64,
                "format": "png"
            })
            plt.close()
            
            # 2. Radar chart des métriques clés
            if len(metrics) >= 3:
                fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection="polar"))
                
                key_metrics = [
                    IntelligenceMetric.SHARPE_RATIO,
                    IntelligenceMetric.WIN_RATE,
                    IntelligenceMetric.PROFIT_FACTOR,
                    IntelligenceMetric.MAX_DRAWDOWN
                ]
                
                values = []
                labels = []
                for km in key_metrics:
                    m = next((m for m in metrics if m.metric == km), None)
                    if m:
                        values.append(m.value)
                        labels.append(m.metric.value.replace("_", " ").title())
                
                if len(values) >= 3:
                    # Normalisation
                    max_val = max(values) if max(values) > 0 else 1
                    normalized = [v / max_val for v in values]
                    
                    angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False).tolist()
                    values_plot = normalized + normalized[:1]
                    angles_plot = angles + angles[:1]
                    
                    ax.plot(angles_plot, values_plot, 'o-', linewidth=2)
                    ax.fill(angles_plot, values_plot, alpha=0.25)
                    ax.set_xticks(angles)
                    ax.set_xticklabels(labels)
                    ax.set_ylim(0, 1)
                    ax.set_title("Key Metrics Radar")
                    
                    plt.tight_layout()
                    
                    buf = BytesIO()
                    plt.savefig(buf, format="png", dpi=self.config["visualization_dpi"])
                    buf.seek(0)
                    img_base64 = base64.b64encode(buf.getvalue()).decode()
                    
                    visualizations.append({
                        "type": IntelligenceVisualizationType.RADAR.value,
                        "title": "Key Metrics Radar",
                        "data": img_base64,
                        "format": "png"
                    })
                    plt.close()
            
            # 3. Gauge chart pour le score global
            if "overall_score" in await self._generate_summary(metrics):
                fig, ax = plt.subplots(figsize=(8, 6))
                
                # Gauge simple avec matplotlib
                overall_score = 3.5  # Exemple
                colors = ["#e74c3c", "#f39c12", "#3498db", "#2ecc71"]
                ax.pie([overall_score, 5 - overall_score], 
                       colors=[colors[min(3, int(overall_score))], "#ecf0f1"],
                       startangle=90, counterclock=False)
                ax.text(0, 0, f"{overall_score:.1f}/5", 
                       ha="center", va="center", fontsize=24, fontweight="bold")
                ax.set_title("Overall Intelligence Score")
                
                plt.tight_layout()
                
                buf = BytesIO()
                plt.savefig(buf, format="png", dpi=self.config["visualization_dpi"])
                buf.seek(0)
                img_base64 = base64.b64encode(buf.getvalue()).decode()
                
                visualizations.append({
                    "type": IntelligenceVisualizationType.GAUGE.value,
                    "title": "Overall Score",
                    "data": img_base64,
                    "format": "png"
                })
                plt.close()
            
        except Exception as e:
            logger.error(f"Visualization generation error: {e}")
        
        return visualizations
    
    async def _generate_insights(self, metrics: List[IntelligenceMetricValue]) -> List[str]:
        """Génère des insights."""
        insights = []
        
        if not metrics:
            return insights
        
        # Analyse des métriques
        for metric in metrics:
            if metric.status == "excellent":
                insights.append(f"Excellent {metric.metric.value.replace('_', ' ')}: {metric.value:.2f}")
            elif metric.status == "critical":
                insights.append(f"Critical {metric.metric.value.replace('_', ' ')}: {metric.value:.2f} - Needs immediate attention")
        
        # Analyse des tendances
        with self._metrics_lock:
            for metric_type, values in self._metrics.items():
                if len(values) >= 5:
                    recent = [v.value for v in values[-5:]]
                    trend = (recent[-1] - recent[0]) / (recent[0] + 0.01)
                    if abs(trend) > 0.1:
                        direction = "improving" if trend > 0 else "declining"
                        insights.append(f"{metric_type.replace('_', ' ')} is {direction} (trend: {trend:.2%})")
        
        return insights
    
    async def _identify_risks(self, metrics: List[IntelligenceMetricValue]) -> List[str]:
        """Identifie les risques."""
        risks = []
        
        for metric in metrics:
            if metric.status == "critical":
                risks.append(f"Critical risk: {metric.metric.value.replace('_', ' ')} at {metric.value:.2f}")
            elif metric.status == "warning":
                risks.append(f"Warning: {metric.metric.value.replace('_', ' ')} at {metric.value:.2f}")
        
        # Vérification des seuils critiques
        max_drawdown = next((m for m in metrics if m.metric == IntelligenceMetric.MAX_DRAWDOWN), None)
        if max_drawdown and max_drawdown.value > 0.15:
            risks.append(f"High drawdown risk: {max_drawdown.value:.2%}")
        
        return risks
    
    async def _generate_recommendations(
        self,
        metrics: List[IntelligenceMetricValue],
        insights: List[str],
        risks: List[str]
    ) -> List[str]:
        """Génère des recommandations."""
        recommendations = []
        
        # Recommandations basées sur les métriques
        for metric in metrics:
            if metric.status == "critical":
                recommendations.append(f"Address critical {metric.metric.value.replace('_', ' ')} immediately")
            elif metric.status == "warning":
                recommendations.append(f"Monitor {metric.metric.value.replace('_', ' ')} closely")
        
        # Recommandations basées sur les risques
        for risk in risks:
            if "drawdown" in risk.lower():
                recommendations.append("Implement tighter stop-losses to control drawdown")
            elif "volatility" in risk.lower():
                recommendations.append("Consider reducing position sizes during high volatility")
        
        # Recommandations générales
        if len(metrics) < 5:
            recommendations.append("Collect more data for better intelligence analysis")
        
        if any(m.status == "excellent" for m in metrics):
            recommendations.append("Leverage excellent performing strategies")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _report_generator_loop(self) -> None:
        """Boucle de génération automatique de rapports."""
        while self._is_running:
            await asyncio.sleep(self.config["report_interval"])
            
            try:
                # Génération du rapport quotidien
                report = await self.generate_report()
                
                # Stockage du rapport
                if self.data_manager:
                    await self.data_manager.store(
                        f"intelligence:report:{report.report_id}",
                        report.to_dict(),
                        DataType.REPORT
                    )
                
                logger.debug("Automatic report generated")
                
            except Exception as e:
                logger.error(f"Report generator error: {e}")
    
    async def _anomaly_scan_loop(self) -> None:
        """Boucle de scan des anomalies."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Récupération des données récentes
                if self.data_manager:
                    data = await self.data_manager.retrieve(
                        "intelligence:data",
                        DataType.METRICS
                    )
                    
                    if data:
                        await self.detect_anomalies(data)
                
            except Exception as e:
                logger.error(f"Anomaly scan error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._viz_cache) > self.config["cache_size"]:
                        keys = list(self._viz_cache.keys())
                        for key in keys[:len(self._viz_cache) - self.config["cache_size"]]:
                            del self._viz_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._metrics_lock:
                    self._stats["total_metrics"] = sum(len(v) for v in self._metrics.values())
                with self._reports_lock:
                    self._stats["total_reports"] = len(self._reports)
                with self._anomalies_lock:
                    self._stats["total_anomalies"] = len(self._anomalies)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "intelligence:stats",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _save_metrics(self) -> None:
        """Sauvegarde les métriques."""
        try:
            if self.data_manager:
                with self._metrics_lock:
                    for metric_type, values in self._metrics.items():
                        await self.data_manager.store(
                            f"intelligence:metrics:{metric_type}",
                            [v.to_dict() for v in values],
                            DataType.METRICS
                        )
                
            logger.info("Metrics saved")
            
        except Exception as e:
            logger.error(f"Save metrics error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_report(self, report_id: str) -> Optional[IntelligenceReport]:
        """Récupère un rapport."""
        with self._reports_lock:
            return self._reports.get(report_id)
    
    async def get_reports(self, limit: int = 10) -> List[IntelligenceReport]:
        """Récupère les rapports récents."""
        with self._reports_lock:
            reports = list(self._reports.values())
            reports.sort(key=lambda r: r.generated_at, reverse=True)
            return reports[:limit]
    
    async def get_anomalies(self, resolved: bool = False) -> List[IntelligenceAnomaly]:
        """Récupère les anomalies."""
        with self._anomalies_lock:
            anomalies = self._anomalies
            if resolved:
                anomalies = [a for a in anomalies if a.resolved]
            else:
                anomalies = [a for a in anomalies if not a.resolved]
            return sorted(anomalies, key=lambda a: a.timestamp, reverse=True)
    
    async def resolve_anomaly(self, anomaly_id: str, note: str = "") -> bool:
        """Résout une anomalie."""
        with self._anomalies_lock:
            for anomaly in self._anomalies:
                if anomaly.anomaly_id == anomaly_id and not anomaly.resolved:
                    anomaly.resolved = True
                    anomaly.resolution_note = note
                    self._stats["anomalies_resolved"] += 1
                    return True
        return False
    
    async def export_report(
        self,
        report_id: str,
        format: str = "pdf"
    ) -> bytes:
        """Exporte un rapport dans différents formats."""
        report = await self.get_report(report_id)
        if not report:
            return b""
        
        # Dans un système réel, on utiliserait reportlab ou autre
        # pour générer des PDF, Excel, etc.
        return json.dumps(report.to_dict()).encode()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._metrics_lock:
            self._stats["metrics_count"] = sum(len(v) for v in self._metrics.values())
        with self._reports_lock:
            self._stats["reports_count"] = len(self._reports)
        with self._anomalies_lock:
            self._stats["anomalies_count"] = len(self._anomalies)
        
        return self._stats.copy()


# ============== FACTORY ==============

class IntelligenceFactory:
    """Factory pour créer des composants d'intelligence."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> IntelligenceEngine:
        """Crée un moteur d'intelligence."""
        engine = IntelligenceEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "IntelligenceMetric",
    "IntelligenceReportType",
    "IntelligenceVisualizationType",
    "IntelligenceMetricValue",
    "IntelligenceReport",
    "IntelligenceAnomaly",
    "IntelligenceEngineInterface",
    "IntelligenceEngine",
    "IntelligenceFactory"
]

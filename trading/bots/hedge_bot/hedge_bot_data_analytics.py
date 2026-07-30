# trading/bots/hedge_bot/hedge_bot_data_analytics.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Analytics Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Analytics Module

This module provides comprehensive data analytics and business intelligence
capabilities for the NEXUS Hedge Bot system. It analyzes trading data,
generates insights, and produces actionable reports.

The module covers:
- Trading Analytics
- Performance Analytics
- Risk Analytics
- Market Analytics
- Portfolio Analytics
- Behavioral Analytics
- Predictive Analytics
- Descriptive Analytics
- Diagnostic Analytics
- Prescriptive Analytics
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


# ============================================================
# DATA ANALYTICS ENUMS
# ============================================================

class AnalyticsType(Enum):
    """Analytics types"""
    DESCRIPTIVE = "descriptive"
    DIAGNOSTIC = "diagnostic"
    PREDICTIVE = "predictive"
    PRESCRIPTIVE = "prescriptive"


class AnalyticsMetric(Enum):
    """Analytics metrics"""
    # Trading Metrics
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    
    # Risk Metrics
    VAR_95 = "var_95"
    VAR_99 = "var_99"
    CVAR_95 = "cvar_95"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    VOLATILITY = "volatility"
    
    # Portfolio Metrics
    DIVERSIFICATION_SCORE = "diversification_score"
    CONCENTRATION = "concentration"
    BETA = "beta"
    ALPHA = "alpha"
    
    # Market Metrics
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLUME = "volume"
    LIQUIDITY = "liquidity"


@dataclass
class AnalyticsResult:
    """Analytics result"""
    name: str
    type: AnalyticsType
    metrics: Dict[str, float]
    insights: List[str]
    recommendations: List[str]
    timestamp: datetime
    data: Optional[pd.DataFrame] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type.value,
            "metrics": self.metrics,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class AnalyticsReport:
    """Analytics report"""
    id: str
    title: str
    period: Dict[str, str]
    results: List[AnalyticsResult]
    summary: Dict[str, Any]
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "period": self.period,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "generated_at": self.generated_at.isoformat(),
        }


# ============================================================
# DATA ANALYTICS ENGINE
# ============================================================

class DataAnalyticsEngine:
    """
    Comprehensive data analytics engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data analytics engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_period = self.config.get("default_period", 30)  # days
        self.risk_free_rate = self.config.get("risk_free_rate", 0.04)
        
        # State
        self.analytics_results: List[AnalyticsResult] = []
        self.analytics_reports: List[AnalyticsReport] = []
        
        logger.info("Data analytics engine initialized")
    
    # ============================================================
    # TRADING ANALYTICS
    # ============================================================
    
    def analyze_trading_performance(
        self,
        trades: List[Dict[str, Any]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> AnalyticsResult:
        """
        Analyze trading performance
        
        Args:
            trades: List of trades
            period_start: Period start
            period_end: Period end
            
        Returns:
            AnalyticsResult
        """
        if period_start is None:
            period_start = datetime.now() - timedelta(days=self.default_period)
        if period_end is None:
            period_end = datetime.now()
        
        # Filter trades by period
        filtered_trades = [
            t for t in trades
            if period_start <= t.get("timestamp", datetime.now()) <= period_end
        ]
        
        if not filtered_trades:
            return AnalyticsResult(
                name="trading_performance",
                type=AnalyticsType.DESCRIPTIVE,
                metrics={},
                insights=["No trades in period"],
                recommendations=["Increase trading activity"],
                timestamp=datetime.now(),
            )
        
        # Calculate metrics
        total_pnl = sum(t.get("pnl", 0) for t in filtered_trades)
        winning_trades = [t for t in filtered_trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in filtered_trades if t.get("pnl", 0) < 0]
        total_trades = len(filtered_trades)
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_wins = sum(t.get("pnl", 0) for t in winning_trades)
        total_losses = sum(abs(t.get("pnl", 0)) for t in losing_trades)
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0
        
        metrics = {
            AnalyticsMetric.TOTAL_RETURN.value: total_pnl,
            AnalyticsMetric.WIN_RATE.value: win_rate,
            AnalyticsMetric.PROFIT_FACTOR.value: profit_factor,
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_wins": total_wins,
            "total_losses": total_losses,
        }
        
        # Generate insights
        insights = []
        if win_rate > 0.6:
            insights.append("High win rate indicates effective strategy")
        elif win_rate < 0.4:
            insights.append("Low win rate suggests strategy may need improvement")
        
        if profit_factor > 1.5:
            insights.append("Strong profit factor indicates good risk-reward ratio")
        elif profit_factor < 1.0:
            insights.append("Profit factor below 1 suggests strategy is losing money")
        
        if avg_win > avg_loss:
            insights.append("Average win greater than average loss (good risk-reward)")
        else:
            insights.append("Average loss exceeds average win (consider adjusting stops)")
        
        # Generate recommendations
        recommendations = []
        if win_rate < 0.5:
            recommendations.append("Consider refining entry criteria to improve win rate")
        if profit_factor < 1.2:
            recommendations.append("Adjust risk-reward ratio to improve profitability")
        if avg_loss > avg_win:
            recommendations.append("Tighten stop losses to reduce average loss")
        
        result = AnalyticsResult(
            name="trading_performance",
            type=AnalyticsType.DESCRIPTIVE,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
            details={
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                },
                "total_trades": total_trades,
            },
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # RISK ANALYTICS
    # ============================================================
    
    def analyze_risk(
        self,
        returns: List[float],
        positions: List[Dict[str, Any]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> AnalyticsResult:
        """
        Analyze risk metrics
        
        Args:
            returns: Return series
            positions: Current positions
            period_start: Period start
            period_end: Period end
            
        Returns:
            AnalyticsResult
        """
        if period_start is None:
            period_start = datetime.now() - timedelta(days=self.default_period)
        if period_end is None:
            period_end = datetime.now()
        
        if not returns:
            return AnalyticsResult(
                name="risk_analysis",
                type=AnalyticsType.DIAGNOSTIC,
                metrics={},
                insights=["No return data available"],
                recommendations=["Collect more data for risk analysis"],
                timestamp=datetime.now(),
            )
        
        # Calculate risk metrics
        returns_array = np.array(returns)
        var_95 = np.percentile(returns_array, 5)
        var_99 = np.percentile(returns_array, 1)
        cvar_95 = np.mean(returns_array[returns_array <= var_95])
        
        # Calculate drawdown
        equity = np.cumprod(1 + returns_array)
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)
        
        # Calculate volatility
        volatility = np.std(returns_array) * np.sqrt(252)
        
        # Calculate Sharpe ratio
        avg_return = np.mean(returns_array) * 252
        sharpe = (avg_return - self.risk_free_rate) / volatility if volatility > 0 else 0
        
        # Calculate Sortino ratio
        downside_returns = returns_array[returns_array < 0]
        downside_std = np.std(downside_returns) * np.sqrt(252)
        sortino = (avg_return - self.risk_free_rate) / downside_std if downside_std > 0 else 0
        
        # Calculate Calmar ratio
        calmar = avg_return / max_drawdown if max_drawdown > 0 else 0
        
        metrics = {
            AnalyticsMetric.VAR_95.value: abs(var_95),
            AnalyticsMetric.VAR_99.value: abs(var_99),
            AnalyticsMetric.CVAR_95.value: abs(cvar_95),
            AnalyticsMetric.MAX_DRAWDOWN.value: max_drawdown,
            AnalyticsMetric.CURRENT_DRAWDOWN.value: drawdown[-1] if len(drawdown) > 0 else 0,
            AnalyticsMetric.VOLATILITY.value: volatility,
            AnalyticsMetric.SHARPE_RATIO.value: sharpe,
            AnalyticsMetric.SORTINO_RATIO.value: sortino,
            AnalyticsMetric.CALMAR_RATIO.value: calmar,
        }
        
        # Generate insights
        insights = []
        if max_drawdown > 0.15:
            insights.append("High max drawdown indicates significant risk")
        else:
            insights.append("Moderate max drawdown is within acceptable range")
        
        if sharpe > 1.5:
            insights.append("Excellent risk-adjusted returns")
        elif sharpe > 0.5:
            insights.append("Good risk-adjusted returns")
        else:
            insights.append("Risk-adjusted returns could be improved")
        
        if var_95 < -0.02:
            insights.append("VaR indicates moderate daily risk")
        
        # Generate recommendations
        recommendations = []
        if max_drawdown > 0.15:
            recommendations.append("Implement stricter drawdown controls")
        if sharpe < 0.5:
            recommendations.append("Improve return or reduce risk to increase Sharpe ratio")
        if volatility > 0.25:
            recommendations.append("Consider reducing position sizes to lower volatility")
        
        result = AnalyticsResult(
            name="risk_analysis",
            type=AnalyticsType.DIAGNOSTIC,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
            details={
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                },
                "n_returns": len(returns),
            },
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # PORTFOLIO ANALYTICS
    # ============================================================
    
    def analyze_portfolio(
        self,
        positions: List[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> AnalyticsResult:
        """
        Analyze portfolio metrics
        
        Args:
            positions: Current positions
            weights: Asset weights
            
        Returns:
            AnalyticsResult
        """
        # Calculate concentration
        sorted_weights = sorted(weights.values(), reverse=True)
        concentration = sum(w ** 2 for w in weights.values())
        
        # Calculate diversification score
        n = len(weights)
        effective_assets = 1 / concentration if concentration > 0 else 0
        diversification_score = min(1.0, effective_assets / n if n > 0 else 0)
        
        # Calculate allocation
        allocation = {}
        for position in positions:
            asset_class = position.get("asset_class", "other")
            value = position.get("value", 0)
            allocation[asset_class] = allocation.get(asset_class, 0) + value
        
        total_value = sum(allocation.values())
        allocation_pct = {
            k: v / total_value if total_value > 0 else 0
            for k, v in allocation.items()
        }
        
        metrics = {
            AnalyticsMetric.DIVERSIFICATION_SCORE.value: diversification_score,
            AnalyticsMetric.CONCENTRATION.value: concentration,
            "effective_assets": effective_assets,
            "total_assets": n,
            "allocation": allocation_pct,
        }
        
        # Generate insights
        insights = []
        if diversification_score > 0.7:
            insights.append("Well-diversified portfolio")
        elif diversification_score > 0.4:
            insights.append("Moderately diversified portfolio")
        else:
            insights.append("Portfolio is concentrated - consider adding more assets")
        
        if concentration > 0.25:
            insights.append("High concentration - risk is not well diversified")
        
        # Generate recommendations
        recommendations = []
        if diversification_score < 0.5:
            recommendations.append("Increase diversification by adding more uncorrelated assets")
        if concentration > 0.25:
            recommendations.append("Reduce largest positions to lower concentration risk")
        
        result = AnalyticsResult(
            name="portfolio_analysis",
            type=AnalyticsType.DESCRIPTIVE,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
            details={
                "positions": positions,
                "weights": weights,
            },
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # MARKET ANALYTICS
    # ============================================================
    
    def analyze_market(
        self,
        market_data: pd.DataFrame,
        symbol: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> AnalyticsResult:
        """
        Analyze market data
        
        Args:
            market_data: Market data
            symbol: Asset symbol
            period_start: Period start
            period_end: Period end
            
        Returns:
            AnalyticsResult
        """
        if period_start is None:
            period_start = datetime.now() - timedelta(days=self.default_period)
        if period_end is None:
            period_end = datetime.now()
        
        # Filter data
        if "timestamp" in market_data.columns:
            market_data = market_data[
                (market_data["timestamp"] >= period_start) &
                (market_data["timestamp"] <= period_end)
            ]
        
        if market_data.empty:
            return AnalyticsResult(
                name="market_analysis",
                type=AnalyticsType.DESCRIPTIVE,
                metrics={},
                insights=["No market data available"],
                recommendations=["Collect market data for analysis"],
                timestamp=datetime.now(),
            )
        
        # Calculate metrics
        close = market_data.get("close", market_data.get("price", market_data.iloc[:, 0]))
        
        if isinstance(close, pd.Series):
            close = close.values
        
        returns = np.diff(np.log(close))
        
        # Calculate trend
        trend = np.polyfit(range(len(close)), close, 1)[0]
        
        # Calculate momentum
        if len(close) >= 10:
            momentum = (close[-1] / close[-10] - 1)
        else:
            momentum = 0
        
        # Calculate volatility
        volatility = np.std(returns) * np.sqrt(252)
        
        # Calculate volume
        volume = market_data.get("volume", [0])
        avg_volume = np.mean(volume) if len(volume) > 0 else 0
        
        metrics = {
            AnalyticsMetric.TREND.value: trend,
            AnalyticsMetric.MOMENTUM.value: momentum,
            AnalyticsMetric.VOLATILITY.value: volatility,
            AnalyticsMetric.VOLUME.value: avg_volume,
            "current_price": close[-1] if len(close) > 0 else 0,
            "price_change": (close[-1] / close[0] - 1) if len(close) > 1 else 0,
        }
        
        # Generate insights
        insights = []
        if trend > 0:
            insights.append("Uptrend detected - bullish sentiment")
        else:
            insights.append("Downtrend detected - bearish sentiment")
        
        if momentum > 0.05:
            insights.append("Strong positive momentum")
        elif momentum < -0.05:
            insights.append("Strong negative momentum")
        
        if volatility > 0.3:
            insights.append("High volatility - increased risk")
        
        # Generate recommendations
        recommendations = []
        if volatility > 0.3:
            recommendations.append("Reduce position sizes in high volatility environment")
        if trend > 0:
            recommendations.append("Consider buying on pullbacks in uptrend")
        else:
            recommendations.append("Consider selling on rallies in downtrend")
        
        result = AnalyticsResult(
            name="market_analysis",
            type=AnalyticsType.DESCRIPTIVE,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
            details={
                "symbol": symbol,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                },
                "data_points": len(market_data),
            },
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # PREDICTIVE ANALYTICS
    # ============================================================
    
    def predict_trend(
        self,
        data: List[float],
        horizon: int = 10
    ) -> AnalyticsResult:
        """
        Predict future trend
        
        Args:
            data: Time series data
            horizon: Prediction horizon
            
        Returns:
            AnalyticsResult
        """
        if len(data) < 20:
            return AnalyticsResult(
                name="trend_prediction",
                type=AnalyticsType.PREDICTIVE,
                metrics={},
                insights=["Insufficient data for trend prediction"],
                recommendations=["Collect more historical data"],
                timestamp=datetime.now(),
            )
        
        # Simple linear regression for trend prediction
        x = np.arange(len(data))
        slope, intercept = np.polyfit(x, data, 1)
        
        # Predict future values
        future_x = np.arange(len(data), len(data) + horizon)
        predictions = slope * future_x + intercept
        
        # Calculate confidence (based on R-squared)
        predicted = slope * x + intercept
        ss_res = np.sum((data - predicted) ** 2)
        ss_tot = np.sum((data - np.mean(data)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        metrics = {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "predictions": predictions.tolist(),
            "horizon": horizon,
        }
        
        # Generate insights
        insights = []
        if slope > 0:
            insights.append("Predicted uptrend continuation")
        else:
            insights.append("Predicted downtrend continuation")
        
        if r_squared > 0.7:
            insights.append("High confidence in trend prediction")
        elif r_squared > 0.4:
            insights.append("Moderate confidence in trend prediction")
        else:
            insights.append("Low confidence - trend may be weak")
        
        # Generate recommendations
        recommendations = []
        if r_squared < 0.5:
            recommendations.append("Use additional indicators for confirmation")
        
        result = AnalyticsResult(
            name="trend_prediction",
            type=AnalyticsType.PREDICTIVE,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
            details={
                "data_points": len(data),
                "horizon": horizon,
            },
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_report(
        self,
        title: str,
        analyses: List[str]
    ) -> AnalyticsReport:
        """
        Generate analytics report
        
        Args:
            title: Report title
            analyses: List of analysis names
            
        Returns:
            AnalyticsReport
        """
        results = []
        for analysis_name in analyses:
            # Find matching results
            matching = [
                r for r in self.analytics_results
                if r.name == analysis_name
            ]
            if matching:
                results.append(matching[-1])  # Latest result
        
        # Generate summary
        summary = {
            "total_analyses": len(results),
            "insights": [],
            "recommendations": [],
            "metrics_summary": {},
        }
        
        for result in results:
            summary["insights"].extend(result.insights)
            summary["recommendations"].extend(result.recommendations)
            for k, v in result.metrics.items():
                if isinstance(v, (int, float)):
                    if k not in summary["metrics_summary"]:
                        summary["metrics_summary"][k] = []
                    summary["metrics_summary"][k].append(v)
        
        # Average metrics
        for k, v in summary["metrics_summary"].items():
            summary["metrics_summary"][k] = np.mean(v) if v else 0
        
        report = AnalyticsReport(
            id=f"report_{int(time.time())}",
            title=title,
            period={
                "start": (datetime.now() - timedelta(days=self.default_period)).isoformat(),
                "end": datetime.now().isoformat(),
            },
            results=results,
            summary=summary,
            generated_at=datetime.now(),
        )
        
        self.analytics_reports.append(report)
        return report
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get analytics statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_analyses": len(self.analytics_results),
            "total_reports": len(self.analytics_reports),
            "analysis_types": {
                t.value: len([r for r in self.analytics_results if r.type == t])
                for t in AnalyticsType
            },
            "last_analysis": self.analytics_results[-1].to_dict() if self.analytics_results else None,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AnalyticsType",
    "AnalyticsMetric",
    
    # Dataclasses
    "AnalyticsResult",
    "AnalyticsReport",
    
    # Classes
    "DataAnalyticsEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

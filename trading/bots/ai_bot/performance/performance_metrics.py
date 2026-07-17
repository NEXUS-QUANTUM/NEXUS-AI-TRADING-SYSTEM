"""
NEXUS AI TRADING SYSTEM - Performance Metrics
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced performance metrics calculator for trading systems, models,
and components with comprehensive statistical analysis and benchmarking.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

from shared.utilities.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics container."""

    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    treynor_ratio: float = 0.0
    information_ratio: float = 0.0
    omega_ratio: float = 0.0
    sterling_ratio: float = 0.0

    # Returns
    total_return: float = 0.0
    annual_return: float = 0.0
    monthly_return: float = 0.0
    weekly_return: float = 0.0
    avg_return: float = 0.0
    median_return: float = 0.0
    std_return: float = 0.0

    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_duration_days: float = 0.0
    avg_drawdown: float = 0.0
    avg_drawdown_duration_days: float = 0.0
    recovery_factor: float = 0.0

    # Win/Loss statistics
    win_rate: float = 0.0
    loss_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Distribution metrics
    skewness: float = 0.0
    kurtosis: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0

    # Trading efficiency
    avg_trade_duration_hours: float = 0.0
    turnover_rate: float = 0.0
    slippage_cost: float = 0.0
    transaction_cost: float = 0.0

    # Model-specific metrics
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    auc_pr: float = 0.0
    mse: float = 0.0
    rmse: float = 0.0
    mae: float = 0.0
    r2_score: float = 0.0
    mape: float = 0.0
    smape: float = 0.0

    # Advanced metrics
    max_risk_exposure: float = 0.0
    avg_risk_exposure: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "risk_adjusted": {
                "sharpe_ratio": self.sharpe_ratio,
                "sortino_ratio": self.sortino_ratio,
                "calmar_ratio": self.calmar_ratio,
                "treynor_ratio": self.treynor_ratio,
                "information_ratio": self.information_ratio,
                "omega_ratio": self.omega_ratio,
                "sterling_ratio": self.sterling_ratio,
            },
            "returns": {
                "total_return": self.total_return,
                "annual_return": self.annual_return,
                "monthly_return": self.monthly_return,
                "weekly_return": self.weekly_return,
                "avg_return": self.avg_return,
                "median_return": self.median_return,
                "std_return": self.std_return,
            },
            "drawdown": {
                "max_drawdown": self.max_drawdown,
                "max_drawdown_duration_days": self.max_drawdown_duration_days,
                "avg_drawdown": self.avg_drawdown,
                "avg_drawdown_duration_days": self.avg_drawdown_duration_days,
                "recovery_factor": self.recovery_factor,
            },
            "win_loss": {
                "win_rate": self.win_rate,
                "loss_rate": self.loss_rate,
                "profit_factor": self.profit_factor,
                "avg_win": self.avg_win,
                "avg_loss": self.avg_loss,
                "win_loss_ratio": self.win_loss_ratio,
                "max_consecutive_wins": self.max_consecutive_wins,
                "max_consecutive_losses": self.max_consecutive_losses,
            },
            "distribution": {
                "skewness": self.skewness,
                "kurtosis": self.kurtosis,
                "var_95": self.var_95,
                "var_99": self.var_99,
                "cvar_95": self.cvar_95,
                "cvar_99": self.cvar_99,
            },
            "efficiency": {
                "avg_trade_duration_hours": self.avg_trade_duration_hours,
                "turnover_rate": self.turnover_rate,
                "slippage_cost": self.slippage_cost,
                "transaction_cost": self.transaction_cost,
            },
            "model": {
                "accuracy": self.accuracy,
                "precision": self.precision,
                "recall": self.recall,
                "f1_score": self.f1_score,
                "auc_roc": self.auc_roc,
                "auc_pr": self.auc_pr,
                "mse": self.mse,
                "rmse": self.rmse,
                "mae": self.mae,
                "r2_score": self.r2_score,
                "mape": self.mape,
                "smape": self.smape,
            },
            "advanced": {
                "max_risk_exposure": self.max_risk_exposure,
                "avg_risk_exposure": self.avg_risk_exposure,
                "beta": self.beta,
                "alpha": self.alpha,
            },
        }


class PerformanceMetricsCalculator:
    """
    Advanced performance metrics calculator for trading systems.
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize the metrics calculator.

        Args:
            risk_free_rate: Risk-free rate (default: 2%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_metrics(
        self,
        returns: Union[List[float], np.ndarray],
        trades: Optional[Union[List[Dict], pd.DataFrame]] = None,
        predictions: Optional[Union[List[float], np.ndarray]] = None,
        actuals: Optional[Union[List[float], np.ndarray]] = None,
        risk_exposure: Optional[Union[List[float], np.ndarray]] = None,
        benchmark_returns: Optional[Union[List[float], np.ndarray]] = None,
        period: str = "daily",
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            returns: List of returns
            trades: List of trade data
            predictions: Model predictions
            actuals: Actual values
            risk_exposure: Risk exposure over time
            benchmark_returns: Benchmark returns
            period: Return period ("daily", "weekly", "monthly")

        Returns:
            PerformanceMetrics object
        """
        metrics = PerformanceMetrics()

        # Convert to numpy arrays
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) == 0:
            logger.warning("No valid returns data")
            return metrics

        # Calculate base metrics
        metrics = self._calculate_return_metrics(metrics, returns, period)
        metrics = self._calculate_risk_metrics(metrics, returns)
        metrics = self._calculate_drawdown_metrics(metrics, returns)

        # Calculate win/loss metrics if trades available
        if trades is not None:
            metrics = self._calculate_trade_metrics(metrics, trades)

        # Calculate distribution metrics
        metrics = self._calculate_distribution_metrics(metrics, returns)

        # Calculate risk-adjusted metrics
        metrics = self._calculate_risk_adjusted_metrics(
            metrics, returns, benchmark_returns, period
        )

        # Calculate model metrics if predictions available
        if predictions is not None and actuals is not None:
            metrics = self._calculate_model_metrics(
                metrics, predictions, actuals
            )

        # Calculate advanced metrics
        if risk_exposure is not None:
            metrics = self._calculate_risk_exposure_metrics(
                metrics, risk_exposure
            )

        if benchmark_returns is not None:
            metrics = self._calculate_beta_alpha_metrics(
                metrics, returns, benchmark_returns
            )

        return metrics

    def _calculate_return_metrics(
        self,
        metrics: PerformanceMetrics,
        returns: np.ndarray,
        period: str,
    ) -> PerformanceMetrics:
        """Calculate return-based metrics."""
        # Basic statistics
        metrics.avg_return = float(np.mean(returns))
        metrics.median_return = float(np.median(returns))
        metrics.std_return = float(np.std(returns))

        # Total return (cumulative)
        metrics.total_return = float(np.prod(1 + returns) - 1)

        # Annualized returns
        periods_per_year = {
            "daily": 252,
            "weekly": 52,
            "monthly": 12,
            "hourly": 252 * 6.5,
        }
        n_periods = periods_per_year.get(period, 252)

        if len(returns) > 0:
            # Annual return
            metrics.annual_return = (
                (1 + metrics.total_return) ** (n_periods / len(returns)) - 1
            )

            # Monthly return (approximate)
            metrics.monthly_return = metrics.annual_return / 12

            # Weekly return
            metrics.weekly_return = metrics.annual_return / 52

        return metrics

    def _calculate_risk_metrics(
        self,
        metrics: PerformanceMetrics,
        returns: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate risk-based metrics."""
        if len(returns) == 0:
            return metrics

        # VaR (95% and 99%)
        metrics.var_95 = float(np.percentile(returns, 5))
        metrics.var_99 = float(np.percentile(returns, 1))

        # CVaR (Expected Shortfall)
        metrics.cvar_95 = float(np.mean(returns[returns <= metrics.var_95]))
        metrics.cvar_99 = float(np.mean(returns[returns <= metrics.var_99]))

        # Skewness and Kurtosis
        metrics.skewness = float(stats.skew(returns))
        metrics.kurtosis = float(stats.kurtosis(returns))

        return metrics

    def _calculate_drawdown_metrics(
        self,
        metrics: PerformanceMetrics,
        returns: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate drawdown metrics."""
        if len(returns) == 0:
            return metrics

        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)

        # Drawdown series
        drawdown = (running_max - cum_returns) / running_max

        # Max drawdown
        metrics.max_drawdown = float(np.max(drawdown))

        # Average drawdown
        metrics.avg_drawdown = float(np.mean(drawdown))

        # Drawdown duration
        if metrics.max_drawdown > 0:
            # Find max drawdown period
            dd_start = None
            dd_end = None

            for i, dd in enumerate(drawdown):
                if dd > 0 and dd_start is None:
                    dd_start = i
                elif dd == 0 and dd_start is not None:
                    dd_end = i
                    break

            if dd_start is not None and dd_end is not None:
                metrics.max_drawdown_duration_days = float(dd_end - dd_start)

            # Average drawdown duration
            dd_periods = []
            in_dd = False
            dd_start = None

            for i, dd in enumerate(drawdown):
                if dd > 0 and not in_dd:
                    in_dd = True
                    dd_start = i
                elif dd == 0 and in_dd:
                    in_dd = False
                    dd_periods.append(i - dd_start)

            if dd_periods:
                metrics.avg_drawdown_duration_days = float(np.mean(dd_periods))

        # Recovery factor
        if metrics.max_drawdown > 0:
            metrics.recovery_factor = float(metrics.total_return / metrics.max_drawdown)

        return metrics

    def _calculate_trade_metrics(
        self,
        metrics: PerformanceMetrics,
        trades: Union[List[Dict], pd.DataFrame],
    ) -> PerformanceMetrics:
        """Calculate trade-based metrics."""
        if isinstance(trades, pd.DataFrame):
            trades = trades.to_dict("records")

        if not trades:
            return metrics

        # Extract trade data
        pnls = []
        durations = []
        winning_trades = []
        losing_trades = []

        for trade in trades:
            pnl = trade.get("pnl", trade.get("profit", 0))
            pnls.append(pnl)

            if pnl > 0:
                winning_trades.append(pnl)
            else:
                losing_trades.append(pnl)

            duration = trade.get("duration_hours", 0)
            if duration > 0:
                durations.append(duration)

        # Win/Loss rates
        total_trades = len(pnls)
        if total_trades > 0:
            metrics.win_rate = float(len(winning_trades) / total_trades)
            metrics.loss_rate = float(len(losing_trades) / total_trades)

            # Profit factor
            total_wins = sum(winning_trades) if winning_trades else 0
            total_losses = abs(sum(losing_trades)) if losing_trades else 1
            metrics.profit_factor = float(total_wins / total_losses)

            # Average win/loss
            metrics.avg_win = float(np.mean(winning_trades)) if winning_trades else 0
            metrics.avg_loss = float(np.mean(losing_trades)) if losing_trades else 0

            # Win/Loss ratio
            if metrics.avg_loss != 0:
                metrics.win_loss_ratio = float(metrics.avg_win / abs(metrics.avg_loss))

            # Consecutive wins/losses
            max_wins = 0
            max_losses = 0
            current_wins = 0
            current_losses = 0

            for pnl in pnls:
                if pnl > 0:
                    current_wins += 1
                    current_losses = 0
                    max_wins = max(max_wins, current_wins)
                else:
                    current_losses += 1
                    current_wins = 0
                    max_losses = max(max_losses, current_losses)

            metrics.max_consecutive_wins = max_wins
            metrics.max_consecutive_losses = max_losses

        # Average trade duration
        if durations:
            metrics.avg_trade_duration_hours = float(np.mean(durations))

        return metrics

    def _calculate_distribution_metrics(
        self,
        metrics: PerformanceMetrics,
        returns: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate distribution metrics."""
        if len(returns) == 0:
            return metrics

        # Skewness and Kurtosis
        metrics.skewness = float(stats.skew(returns))
        metrics.kurtosis = float(stats.kurtosis(returns))

        return metrics

    def _calculate_risk_adjusted_metrics(
        self,
        metrics: PerformanceMetrics,
        returns: np.ndarray,
        benchmark_returns: Optional[np.ndarray],
        period: str,
    ) -> PerformanceMetrics:
        """Calculate risk-adjusted return metrics."""
        if len(returns) == 0:
            return metrics

        # Periods per year
        periods_per_year = {
            "daily": 252,
            "weekly": 52,
            "monthly": 12,
            "hourly": 252 * 6.5,
        }
        n_periods = periods_per_year.get(period, 252)

        # Sharpe Ratio
        excess_returns = returns - self.risk_free_rate / n_periods
        if np.std(excess_returns) > 0:
            metrics.sharpe_ratio = float(
                np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(n_periods)
            )

        # Sortino Ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            metrics.sortino_ratio = float(
                (np.mean(returns) - self.risk_free_rate / n_periods)
                / np.std(downside_returns)
                * np.sqrt(n_periods)
            )

        # Calmar Ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = float(metrics.annual_return / metrics.max_drawdown)

        # Omega Ratio
        threshold = self.risk_free_rate / n_periods
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        if len(losses) > 0 and np.sum(losses) > 0:
            metrics.omega_ratio = float(np.sum(gains) / np.sum(losses))

        # Sterling Ratio
        avg_dd = metrics.avg_drawdown or 0.01
        metrics.sterling_ratio = float(
            metrics.annual_return / (avg_dd + 0.1)
        )

        # Information Ratio (if benchmark available)
        if benchmark_returns is not None and len(benchmark_returns) == len(returns):
            excess = returns - benchmark_returns
            if np.std(excess) > 0:
                metrics.information_ratio = float(
                    np.mean(excess) / np.std(excess) * np.sqrt(n_periods)
                )

        # Treynor Ratio
        if hasattr(metrics, "beta") and metrics.beta > 0:
            metrics.treynor_ratio = float(
                (metrics.annual_return - self.risk_free_rate) / metrics.beta
            )

        return metrics

    def _calculate_model_metrics(
        self,
        metrics: PerformanceMetrics,
        predictions: Union[List[float], np.ndarray],
        actuals: Union[List[float], np.ndarray],
    ) -> PerformanceMetrics:
        """Calculate model performance metrics."""
        predictions = np.array(predictions)
        actuals = np.array(actuals)

        # Remove NaN values
        valid_mask = ~(np.isnan(predictions) | np.isnan(actuals))
        predictions = predictions[valid_mask]
        actuals = actuals[valid_mask]

        if len(predictions) == 0:
            return metrics

        # Classification metrics (if binary classification)
        unique_values = np.unique(actuals)
        if len(unique_values) <= 2:
            # Binary classification
            from sklearn.metrics import (
                accuracy_score,
                precision_score,
                recall_score,
                f1_score,
                roc_auc_score,
                precision_recall_curve,
                auc,
            )

            # Convert predictions to binary
            pred_binary = np.where(predictions > 0.5, 1, 0).astype(int)
            actual_binary = actuals.astype(int)

            metrics.accuracy = float(accuracy_score(actual_binary, pred_binary))
            metrics.precision = float(precision_score(actual_binary, pred_binary, zero_division=0))
            metrics.recall = float(recall_score(actual_binary, pred_binary, zero_division=0))
            metrics.f1_score = float(f1_score(actual_binary, pred_binary, zero_division=0))

            try:
                metrics.auc_roc = float(roc_auc_score(actual_binary, predictions))
            except Exception:
                metrics.auc_roc = 0.5

            try:
                precision, recall, _ = precision_recall_curve(actual_binary, predictions)
                metrics.auc_pr = float(auc(recall, precision))
            except Exception:
                metrics.auc_pr = 0.0

        else:
            # Regression metrics
            metrics.mse = float(np.mean((predictions - actuals) ** 2))
            metrics.rmse = float(np.sqrt(metrics.mse))
            metrics.mae = float(np.mean(np.abs(predictions - actuals)))

            # R² Score
            ss_res = np.sum((actuals - predictions) ** 2)
            ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
            metrics.r2_score = float(1 - ss_res / ss_tot if ss_tot != 0 else 0)

            # MAPE
            with np.errstate(divide="ignore", invalid="ignore"):
                mape = np.mean(np.abs((actuals - predictions) / actuals)) * 100
                metrics.mape = float(np.nan_to_num(mape, nan=0.0, posinf=0.0))

            # SMAPE
            denominator = np.abs(actuals) + np.abs(predictions)
            with np.errstate(divide="ignore", invalid="ignore"):
                smape = np.mean(2 * np.abs(predictions - actuals) / denominator) * 100
                metrics.smape = float(np.nan_to_num(smape, nan=0.0, posinf=0.0))

        return metrics

    def _calculate_risk_exposure_metrics(
        self,
        metrics: PerformanceMetrics,
        risk_exposure: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate risk exposure metrics."""
        if len(risk_exposure) == 0:
            return metrics

        metrics.max_risk_exposure = float(np.max(risk_exposure))
        metrics.avg_risk_exposure = float(np.mean(risk_exposure))

        return metrics

    def _calculate_beta_alpha_metrics(
        self,
        metrics: PerformanceMetrics,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate Beta and Alpha."""
        if len(returns) != len(benchmark_returns):
            return metrics

        # Remove NaN values
        valid_mask = ~(np.isnan(returns) | np.isnan(benchmark_returns))
        returns = returns[valid_mask]
        benchmark_returns = benchmark_returns[valid_mask]

        if len(returns) < 2:
            return metrics

        # Calculate Beta (covariance / variance)
        cov_matrix = np.cov(returns, benchmark_returns)
        if cov_matrix[1, 1] > 0:
            metrics.beta = float(cov_matrix[0, 1] / cov_matrix[1, 1])

            # Calculate Alpha (annualized)
            beta = metrics.beta
            avg_return = np.mean(returns)
            avg_benchmark = np.mean(benchmark_returns)

            # Alpha = avg_return - (risk_free_rate + beta * (avg_benchmark - risk_free_rate))
            # But we use annualized values
            periods_per_year = 252  # Assuming daily returns
            annual_avg_return = avg_return * periods_per_year
            annual_avg_benchmark = avg_benchmark * periods_per_year

            metrics.alpha = float(
                annual_avg_return
                - (self.risk_free_rate + beta * (annual_avg_benchmark - self.risk_free_rate))
            )

        return metrics


class PerformanceVisualizer:
    """
    Visualization tools for performance metrics.
    """

    def __init__(self, metrics: Optional[PerformanceMetrics] = None):
        """
        Initialize the visualizer.

        Args:
            metrics: Performance metrics to visualize
        """
        self.metrics = metrics

    def plot_equity_curve(
        self,
        returns: np.ndarray,
        title: str = "Equity Curve",
        figsize: Tuple[int, int] = (12, 6),
    ):
        """Plot equity curve."""
        try:
            import matplotlib.pyplot as plt

            cum_returns = np.cumprod(1 + returns)
            fig, ax = plt.subplots(figsize=figsize)

            ax.plot(cum_returns, label="Equity Curve")
            ax.axhline(y=1, color="gray", linestyle="--", alpha=0.5)
            ax.set_title(title)
            ax.set_xlabel("Time")
            ax.set_ylabel("Equity")
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            return fig, ax

        except ImportError:
            logger.warning("matplotlib not available")
            return None, None

    def plot_drawdown(
        self,
        returns: np.ndarray,
        title: str = "Drawdown",
        figsize: Tuple[int, int] = (12, 6),
    ):
        """Plot drawdown."""
        try:
            import matplotlib.pyplot as plt

            cum_returns = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cum_returns)
            drawdown = (running_max - cum_returns) / running_max * 100

            fig, ax = plt.subplots(figsize=figsize)

            ax.fill_between(range(len(drawdown)), 0, drawdown, color="red", alpha=0.3)
            ax.plot(drawdown, color="red", alpha=0.7)
            ax.set_title(title)
            ax.set_xlabel("Time")
            ax.set_ylabel("Drawdown (%)")
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            return fig, ax

        except ImportError:
            logger.warning("matplotlib not available")
            return None, None

    def plot_returns_distribution(
        self,
        returns: np.ndarray,
        title: str = "Returns Distribution",
        figsize: Tuple[int, int] = (12, 6),
    ):
        """Plot returns distribution."""
        try:
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

            # Histogram
            ax1.hist(returns, bins=50, alpha=0.7, color="blue")
            ax1.axvline(x=np.mean(returns), color="red", linestyle="--", label="Mean")
            ax1.axvline(x=np.median(returns), color="green", linestyle="--", label="Median")
            ax1.set_title("Returns Distribution")
            ax1.set_xlabel("Return")
            ax1.set_ylabel("Frequency")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # QQ Plot
            stats.probplot(returns, dist="norm", plot=ax2)
            ax2.set_title("Q-Q Plot")

            plt.tight_layout()
            return fig, (ax1, ax2)

        except ImportError:
            logger.warning("matplotlib not available")
            return None, None

    def plot_monthly_returns_heatmap(
        self,
        returns: np.ndarray,
        dates: List[datetime],
        title: str = "Monthly Returns Heatmap",
        figsize: Tuple[int, int] = (12, 8),
    ):
        """Plot monthly returns heatmap."""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns

            # Group returns by month
            df = pd.DataFrame({
                "return": returns,
                "date": dates,
            })
            df["year"] = df["date"].dt.year
            df["month"] = df["date"].dt.month

            monthly_returns = df.pivot_table(
                values="return",
                index="month",
                columns="year",
                aggfunc="sum",
            )

            fig, ax = plt.subplots(figsize=figsize)
            sns.heatmap(
                monthly_returns,
                annot=True,
                fmt=".2%",
                cmap="RdYlGn",
                center=0,
                ax=ax,
            )
            ax.set_title(title)
            plt.tight_layout()
            return fig, ax

        except ImportError:
            logger.warning("matplotlib/seaborn not available")
            return None, None

    def print_summary(self):
        """Print performance summary."""
        if self.metrics is None:
            return

        print("=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)

        print("\nRisk-Adjusted Returns:")
        print(f"  Sharpe Ratio:  {self.metrics.sharpe_ratio:.3f}")
        print(f"  Sortino Ratio: {self.metrics.sortino_ratio:.3f}")
        print(f"  Calmar Ratio:  {self.metrics.calmar_ratio:.3f}")
        print(f"  Omega Ratio:   {self.metrics.omega_ratio:.3f}")

        print("\nReturns:")
        print(f"  Total Return:    {self.metrics.total_return:.2%}")
        print(f"  Annual Return:   {self.metrics.annual_return:.2%}")
        print(f"  Avg Return:      {self.metrics.avg_return:.4f}")
        print(f"  Std Return:      {self.metrics.std_return:.4f}")

        print("\nDrawdown:")
        print(f"  Max Drawdown:    {self.metrics.max_drawdown:.2%}")
        print(f"  Avg Drawdown:    {self.metrics.avg_drawdown:.2%}")
        print(f"  Recovery Factor: {self.metrics.recovery_factor:.3f}")

        print("\nWin/Loss:")
        print(f"  Win Rate:        {self.metrics.win_rate:.2%}")
        print(f"  Profit Factor:   {self.metrics.profit_factor:.3f}")
        print(f"  Avg Win:         {self.metrics.avg_win:.4f}")
        print(f"  Avg Loss:        {self.metrics.avg_loss:.4f}")
        print(f"  Win/Loss Ratio:  {self.metrics.win_loss_ratio:.3f}")

        print("\nDistribution:")
        print(f"  Skewness:        {self.metrics.skewness:.3f}")
        print(f"  Kurtosis:        {self.metrics.kurtosis:.3f}")
        print(f"  VaR (95%):       {self.metrics.var_95:.4f}")
        print(f"  CVaR (95%):      {self.metrics.cvar_95:.4f}")

        if self.metrics.accuracy > 0:
            print("\nModel Metrics:")
            print(f"  Accuracy:        {self.metrics.accuracy:.3f}")
            print(f"  F1 Score:        {self.metrics.f1_score:.3f}")
            print(f"  AUC-ROC:         {self.metrics.auc_roc:.3f}")

        print("=" * 80)


# Utility function to calculate rolling Sharpe ratio
def rolling_sharpe_ratio(
    returns: np.ndarray,
    window: int = 252,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> np.ndarray:
    """
    Calculate rolling Sharpe ratio.

    Args:
        returns: Array of returns
        window: Rolling window size
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Rolling Sharpe ratio array
    """
    sharpe_ratios = np.full(len(returns), np.nan)

    for i in range(window, len(returns) + 1):
        window_returns = returns[i - window:i]
        excess_returns = window_returns - risk_free_rate / periods_per_year

        if np.std(excess_returns) > 0:
            sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year)
            sharpe_ratios[i - 1] = sharpe

    return sharpe_ratios

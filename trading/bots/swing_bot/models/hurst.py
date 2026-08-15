"""
Swing Bot Hurst Model
=======================

This module provides Hurst exponent analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class HurstMetrics:
    """Hurst metrics data structure."""
    timestamp: datetime
    hurst_exponent: float
    rescaled_range: float
    detrended_fluctuation: float
    generalized_hurst: float
    local_hurst: float
    multifractal_index: float
    predictability: float
    trend_strength: float


@dataclass
class HurstSignal:
    """Hurst trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: HurstMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class HurstModel:
    """
    Hurst exponent analysis model for market memory.
    
    Implements Hurst exponent analysis for market dynamics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Hurst model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[HurstMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Hurst metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Hurst analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(df)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _calculate_metrics(self, df: pd.DataFrame) -> HurstMetrics:
        """
        Calculate Hurst metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            HurstMetrics object
        """
        close = df['close'].values
        
        # Calculate Hurst exponent using R/S method
        hurst = self._calculate_hurst_rs(close)
        
        # Calculate rescaled range
        rs = self._calculate_rescaled_range(close)
        
        # Calculate detrended fluctuation
        df = self._calculate_detrended_fluctuation(close)
        
        # Calculate generalized Hurst
        gh = self._calculate_generalized_hurst(close)
        
        # Calculate local Hurst
        lh = self._calculate_local_hurst(close)
        
        # Calculate multifractal index
        mfi = self._calculate_multifractal_index(close)
        
        # Calculate predictability
        predictability = hurst / 0.5
        
        # Calculate trend strength
        trend_strength = 2 * (hurst - 0.5)
        
        metrics = HurstMetrics(
            timestamp=datetime.now(),
            hurst_exponent=hurst,
            rescaled_range=rs,
            detrended_fluctuation=df,
            generalized_hurst=gh,
            local_hurst=lh,
            multifractal_index=mfi,
            predictability=predictability,
            trend_strength=trend_strength
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_hurst_rs(self, data: np.ndarray) -> float:
        """
        Calculate Hurst exponent using R/S method.
        
        Args:
            data: Time series data
            
        Returns:
            Hurst exponent
        """
        if len(data) < 10:
            return 0.5
        
        n = len(data)
        max_lag = int(np.log10(n)) * 2
        lags = range(10, max_lag + 1, max(1, max_lag // 20))
        
        rs_values = []
        
        for lag in lags:
            # Calculate R/S
            segments = n // lag
            if segments < 2:
                break
            
            rs = 0
            for i in range(segments):
                start = i * lag
                end = start + lag
                segment = data[start:end]
                
                # Calculate mean
                mean = np.mean(segment)
                
                # Calculate cumulative deviation
                deviations = segment - mean
                cum_dev = np.cumsum(deviations)
                
                # Calculate range
                R = np.max(cum_dev) - np.min(cum_dev)
                
                # Calculate standard deviation
                S = np.std(segment)
                
                if S > 0:
                    rs += R / S
            
            rs /= segments
            rs_values.append((np.log(lag), np.log(rs)))
        
        if len(rs_values) < 2:
            return 0.5
        
        # Linear regression
        x = [v[0] for v in rs_values]
        y = [v[1] for v in rs_values]
        slope, intercept = MathUtils.linear_regression(x, y)
        
        return slope
    
    def _calculate_rescaled_range(self, data: np.ndarray) -> float:
        """
        Calculate rescaled range.
        
        Args:
            data: Time series data
            
        Returns:
            Rescaled range
        """
        if len(data) < 10:
            return 0.0
        
        mean = np.mean(data)
        deviations = data - mean
        cum_dev = np.cumsum(deviations)
        R = np.max(cum_dev) - np.min(cum_dev)
        S = np.std(data)
        
        if S > 0:
            return R / S
        else:
            return 0.0
    
    def _calculate_detrended_fluctuation(self, data: np.ndarray) -> float:
        """
        Calculate detrended fluctuation.
        
        Args:
            data: Time series data
            
        Returns:
            Detrended fluctuation
        """
        if len(data) < 20:
            return 0.0
        
        # Calculate integrated series
        integrated = np.cumsum(data - np.mean(data))
        
        # Calculate fluctuation for different scales
        scales = np.logspace(1, np.log10(len(integrated) // 4), 10).astype(int)
        fluctuations = []
        
        for scale in scales:
            if scale < 2 or scale > len(integrated):
                continue
            
            n_segments = len(integrated) // scale
            if n_segments < 2:
                continue
            
            variance = 0
            for i in range(n_segments):
                start = i * scale
                end = start + scale
                segment = integrated[start:end]
                
                # Fit linear trend
                x = np.arange(len(segment))
                slope, intercept = MathUtils.linear_regression(x, segment)
                trend = slope * x + intercept
                
                # Calculate detrended variance
                variance += np.mean((segment - trend) ** 2)
            
            variance /= n_segments
            fluctuations.append((np.log(scale), 0.5 * np.log(variance)))
        
        if len(fluctuations) < 2:
            return 0.0
        
        # Linear regression
        x = [v[0] for v in fluctuations]
        y = [v[1] for v in fluctuations]
        slope, intercept = MathUtils.linear_regression(x, y)
        
        return slope
    
    def _calculate_generalized_hurst(self, data: np.ndarray) -> float:
        """
        Calculate generalized Hurst exponent.
        
        Args:
            data: Time series data
            
        Returns:
            Generalized Hurst exponent
        """
        if len(data) < 50:
            return 0.5
        
        # Calculate for different q values
        q_values = [-2, -1, 1, 2]
        hursts = []
        
        for q in q_values:
            if q == 0:
                continue
            
            # Calculate q-th order moments
            moments = []
            lags = range(10, len(data) // 4, len(data) // 20)
            
            for lag in lags:
                if lag < 2:
                    continue
                
                # Calculate increments
                increments = data[lag:] - data[:-lag]
                if q > 0:
                    moment = np.mean(increments ** q)
                else:
                    moment = np.mean(1 / (increments ** (-q) + 1e-10))
                
                if moment > 0:
                    moments.append((np.log(lag), np.log(moment) / q))
            
            if len(moments) < 2:
                continue
            
            # Linear regression
            x = [m[0] for m in moments]
            y = [m[1] for m in moments]
            slope, intercept = MathUtils.linear_regression(x, y)
            hursts.append(slope)
        
        if hursts:
            return np.mean(hursts)
        else:
            return 0.5
    
    def _calculate_local_hurst(self, data: np.ndarray) -> float:
        """
        Calculate local Hurst exponent.
        
        Args:
            data: Time series data
            
        Returns:
            Local Hurst exponent
        """
        if len(data) < 20:
            return 0.5
        
        # Use sliding window
        window_size = 30
        hursts = []
        
        for i in range(0, len(data) - window_size + 1, window_size // 2):
            window = data[i:i + window_size]
            if len(window) >= 10:
                hurst = self._calculate_hurst_rs(window)
                hursts.append(hurst)
        
        if hursts:
            return np.mean(hursts)
        else:
            return 0.5
    
    def _calculate_multifractal_index(self, data: np.ndarray) -> float:
        """
        Calculate multifractal index.
        
        Args:
            data: Time series data
            
        Returns:
            Multifractal index
        """
        if len(data) < 50:
            return 0.0
        
        # Calculate spectrum
        q_values = np.linspace(-5, 5, 11)
        tau = []
        
        for q in q_values:
            if q == 0:
                continue
            
            moments = []
            lags = range(10, len(data) // 4, len(data) // 20)
            
            for lag in lags:
                if lag < 2:
                    continue
                
                increments = data[lag:] - data[:-lag]
                if q > 0:
                    moment = np.mean(increments ** q)
                else:
                    moment = np.mean(1 / (increments ** (-q) + 1e-10))
                
                if moment > 0:
                    moments.append((np.log(lag), np.log(moment)))
            
            if len(moments) < 2:
                continue
            
            x = [m[0] for m in moments]
            y = [m[1] for m in moments]
            slope, intercept = MathUtils.linear_regression(x, y)
            tau.append(slope)
        
        if not tau:
            return 0.0
        
        # Calculate multifractal index (width of spectrum)
        tau = np.array(tau)
        q_values = q_values[q_values != 0]
        
        # Calculate singularity spectrum
        alpha = np.gradient(tau, q_values)
        f_alpha = alpha * q_values - tau
        
        # Multifractal index is the width of the spectrum
        if len(alpha) > 0:
            return np.max(alpha) - np.min(alpha)
        else:
            return 0.0
    
    def _get_default_metrics(self) -> HurstMetrics:
        """
        Get default metrics.
        
        Returns:
            Default HurstMetrics object
        """
        return HurstMetrics(
            timestamp=datetime.now(),
            hurst_exponent=0.5,
            rescaled_range=0.0,
            detrended_fluctuation=0.0,
            generalized_hurst=0.5,
            local_hurst=0.5,
            multifractal_index=0.0,
            predictability=1.0,
            trend_strength=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: HurstMetrics) -> List[HurstSignal]:
        """
        Generate trading signals from Hurst metrics.
        
        Args:
            df: OHLCV data
            metrics: HurstMetrics object
            
        Returns:
            List of HurstSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check Hurst exponent
        h = metrics.hurst_exponent
        
        if h > 0.6:
            signal_type = 'buy'
            reason = f"Persistent trend (Hurst: {h:.3f})"
            confidence = min((h - 0.5) * 5, 1.0)
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif h < 0.4:
            signal_type = 'sell'
            reason = f"Mean reverting (Hurst: {h:.3f})"
            confidence = min((0.5 - h) * 5, 1.0)
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(HurstSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            metrics=metrics,
            indicators={
                'hurst': h,
                'predictability': metrics.predictability,
                'trend_strength': metrics.trend_strength,
                'local_hurst': metrics.local_hurst
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: HurstMetrics) -> str:
        """
        Get status from Hurst metrics.
        
        Args:
            metrics: HurstMetrics object
            
        Returns:
            Status string
        """
        h = metrics.hurst_exponent
        
        if h > 0.6:
            return 'persistent'
        elif h > 0.5:
            return 'slightly_persistent'
        elif h > 0.4:
            return 'slightly_mean_reverting'
        else:
            return 'mean_reverting'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: HurstMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: HurstMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'persistent': "Persistent market - strong trends",
            'slightly_persistent': "Slightly persistent market",
            'slightly_mean_reverting': "Slightly mean-reverting market",
            'mean_reverting': "Mean-reverting market - range bound"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get Hurst metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_hurst': np.mean([m.hurst_exponent for m in self.metrics_history]),
            'average_predictability': np.mean([m.predictability for m in self.metrics_history]),
            'average_trend_strength': np.mean([m.trend_strength for m in self.metrics_history]),
            'max_hurst': max([m.hurst_exponent for m in self.metrics_history]),
            'min_hurst': min([m.hurst_exponent for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_hurst_model(config: Optional[Dict[str, Any]] = None) -> HurstModel:
    """
    Create a Hurst model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        HurstModel instance
    """
    return HurstModel(config)


__all__ = [
    'HurstMetrics',
    'HurstSignal',
    'HurstModel',
    'create_hurst_model'
]

"""
Swing Bot Sector Model
========================

This module provides sector analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class SectorMetrics:
    """Sector metrics data structure."""
    sector: str
    performance: float
    momentum: float
    relative_strength: float
    valuation: float
    sentiment: float
    flow: float
    volatility: float
    timestamp: datetime


@dataclass
class SectorRotation:
    """Sector rotation data structure."""
    from_sector: str
    to_sector: str
    rotation_score: float
    confidence: float
    timestamp: datetime


@dataclass
class SectorSignal:
    """Sector trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    sector: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class SectorModel:
    """
    Sector analysis model for sector rotation and selection.
    
    Implements sector performance analysis and rotation strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the sector model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.sectors = self.config.get('sectors', ['technology', 'financials', 'healthcare', 
                                                   'energy', 'consumer', 'industrials',
                                                   'utilities', 'materials', 'real_estate'])
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.sector_history: Dict[str, List[SectorMetrics]] = {}
        
        for sector in self.sectors:
            self.sector_history[sector] = []
        
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze sector performance.
        
        Args:
            df_dict: Dictionary of sector dataframes
            
        Returns:
            Sector analysis results
        """
        if not df_dict:
            return {'metrics': [], 'signals': [], 'rotations': []}
        
        # Calculate metrics for each sector
        metrics = []
        for sector, df in df_dict.items():
            if sector in self.sectors:
                metric = self._calculate_sector_metrics(sector, df)
                metrics.append(metric)
                if sector in self.sector_history:
                    self.sector_history[sector].append(metric)
        
        # Identify sector rotations
        rotations = self._detect_rotations(metrics)
        
        # Generate signals
        signals = self._generate_signals(df_dict, metrics, rotations)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'rotations': rotations,
            'top_sectors': self._get_top_sectors(metrics),
            'bottom_sectors': self._get_bottom_sectors(metrics),
            'market_character': self._get_market_character(metrics)
        }
    
    def _calculate_sector_metrics(self, sector: str, df: pd.DataFrame) -> SectorMetrics:
        """
        Calculate metrics for a sector.
        
        Args:
            sector: Sector name
            df: Sector data
            
        Returns:
            SectorMetrics object
        """
        if len(df) < self.lookback_period:
            return SectorMetrics(
                sector=sector,
                performance=0.0,
                momentum=0.0,
                relative_strength=0.0,
                valuation=0.0,
                sentiment=0.0,
                flow=0.0,
                volatility=0.0,
                timestamp=datetime.now()
            )
        
        close = df['close'].values
        volume = df['volume'].values
        
        # Calculate performance
        performance = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        
        # Calculate momentum
        momentum = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0
        
        # Calculate relative strength (compared to benchmark)
        # This would use actual benchmark data in production
        relative_strength = performance * 0.5 + momentum * 0.5
        
        # Calculate valuation (placeholder)
        valuation = 0.5
        
        # Calculate sentiment (placeholder)
        sentiment = 0.5
        
        # Calculate flow (placeholder)
        flow = volume[-1] / np.mean(volume[-self.lookback_period:]) if np.mean(volume[-self.lookback_period:]) > 0 else 1
        
        # Calculate volatility
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-self.lookback_period:]) * np.sqrt(252)
        
        return SectorMetrics(
            sector=sector,
            performance=performance,
            momentum=momentum,
            relative_strength=relative_strength,
            valuation=valuation,
            sentiment=sentiment,
            flow=flow,
            volatility=volatility,
            timestamp=datetime.now()
        )
    
    def _detect_rotations(self, metrics: List[SectorMetrics]) -> List[SectorRotation]:
        """
        Detect sector rotations.
        
        Args:
            metrics: List of sector metrics
            
        Returns:
            List of SectorRotation objects
        """
        rotations = []
        
        if len(metrics) < 2:
            return rotations
        
        # Sort sectors by performance
        sorted_sectors = sorted(metrics, key=lambda x: x.performance, reverse=True)
        
        # Identify rotation from worst to best
        if len(sorted_sectors) >= 2:
            worst_sector = sorted_sectors[-1]
            best_sector = sorted_sectors[0]
            
            # Calculate rotation score
            performance_diff = best_sector.performance - worst_sector.performance
            momentum_diff = best_sector.momentum - worst_sector.momentum
            
            rotation_score = performance_diff * 0.6 + momentum_diff * 0.4
            confidence = min(abs(rotation_score) * 5, 1.0)
            
            if confidence > self.confidence_threshold:
                rotations.append(SectorRotation(
                    from_sector=worst_sector.sector,
                    to_sector=best_sector.sector,
                    rotation_score=rotation_score,
                    confidence=confidence,
                    timestamp=datetime.now()
                ))
        
        return rotations
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame],
                         metrics: List[SectorMetrics],
                         rotations: List[SectorRotation]) -> List[SectorSignal]:
        """
        Generate trading signals from sector analysis.
        
        Args:
            df_dict: Dictionary of sector dataframes
            metrics: List of sector metrics
            rotations: List of sector rotations
            
        Returns:
            List of SectorSignal objects
        """
        signals = []
        
        if not metrics or not rotations:
            return signals
        
        # Get best sector to rotate into
        top_rotation = rotations[0] if rotations else None
        
        if not top_rotation:
            return signals
        
        # Generate signal for the sector to rotate into
        sector = top_rotation.to_sector
        if sector not in df_dict:
            return signals
        
        df = df_dict[sector]
        if len(df) < 20:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        signal_type = 'buy'
        reason = f"Sector rotation into {sector} detected"
        confidence = top_rotation.confidence
        
        target = current_price * (1 + confidence * 0.05)
        stop_loss = current_price * (1 - confidence * 0.03)
        
        signals.append(SectorSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            sector=sector,
            indicators={
                'rotation_score': top_rotation.rotation_score,
                'from_sector': top_rotation.from_sector
            }
        ))
        
        return signals
    
    def _get_top_sectors(self, metrics: List[SectorMetrics]) -> List[Dict[str, Any]]:
        """
        Get top performing sectors.
        
        Args:
            metrics: List of sector metrics
            
        Returns:
            List of top sectors
        """
        if not metrics:
            return []
        
        sorted_metrics = sorted(metrics, key=lambda x: x.performance, reverse=True)
        return [
            {
                'sector': m.sector,
                'performance': m.performance,
                'momentum': m.momentum,
                'relative_strength': m.relative_strength
            }
            for m in sorted_metrics[:3]
        ]
    
    def _get_bottom_sectors(self, metrics: List[SectorMetrics]) -> List[Dict[str, Any]]:
        """
        Get bottom performing sectors.
        
        Args:
            metrics: List of sector metrics
            
        Returns:
            List of bottom sectors
        """
        if not metrics:
            return []
        
        sorted_metrics = sorted(metrics, key=lambda x: x.performance)
        return [
            {
                'sector': m.sector,
                'performance': m.performance,
                'momentum': m.momentum,
                'relative_strength': m.relative_strength
            }
            for m in sorted_metrics[:3]
        ]
    
    def _get_market_character(self, metrics: List[SectorMetrics]) -> str:
        """
        Get market character description.
        
        Args:
            metrics: List of sector metrics
            
        Returns:
            Market character description
        """
        if not metrics:
            return "No sector data available"
        
        # Calculate average performance
        avg_performance = np.mean([m.performance for m in metrics])
        
        if avg_performance > 0.05:
            return "Bullish market - strong sector performance"
        elif avg_performance > 0.0:
            return "Moderate market - slight sector gains"
        elif avg_performance > -0.05:
            return "Moderate market - slight sector losses"
        else:
            return "Bearish market - weak sector performance"
    
    def get_sector_summary(self) -> Dict[str, Any]:
        """
        Get sector summary.
        
        Returns:
            Sector summary
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'sectors': {}
        }
        
        for sector, history in self.sector_history.items():
            if history:
                latest = history[-1]
                summary['sectors'][sector] = {
                    'performance': latest.performance,
                    'momentum': latest.momentum,
                    'relative_strength': latest.relative_strength,
                    'volatility': latest.volatility,
                    'trend': 'up' if latest.momentum > 0 else 'down',
                    'history_length': len(history)
                }
        
        return summary


def create_sector_model(config: Optional[Dict[str, Any]] = None) -> SectorModel:
    """
    Create a sector model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SectorModel instance
    """
    return SectorModel(config)


__all__ = [
    'SectorMetrics',
    'SectorRotation',
    'SectorSignal',
    'SectorModel',
    'create_sector_model'
]

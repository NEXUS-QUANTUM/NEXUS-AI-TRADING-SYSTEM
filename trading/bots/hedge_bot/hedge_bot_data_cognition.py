# trading/bots/hedge_bot/hedge_bot_data_cognition.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Cognition Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Cognition Module

This module provides comprehensive cognitive data processing and understanding
capabilities for the NEXUS Hedge Bot system. It applies cognitive computing
techniques to understand market patterns and behaviors.

The module covers:
- Cognitive Pattern Recognition
- Market Understanding
- Behavioral Pattern Analysis
- Anomaly Detection
- Pattern Learning
- Cognitive Reasoning
- Market Psychology Analysis
- Sentiment Understanding
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
from collections import deque

# Try to import ML libraries
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ============================================================
# DATA COGNITION ENUMS
# ============================================================

class CognitionType(Enum):
    """Cognition types"""
    PATTERN_RECOGNITION = "pattern_recognition"
    ANOMALY_DETECTION = "anomaly_detection"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    MARKET_UNDERSTANDING = "market_understanding"
    PSYCHOLOGICAL_ANALYSIS = "psychological_analysis"


class PatternType(Enum):
    """Pattern types"""
    TREND = "trend"
    REVERSAL = "reversal"
    CONTINUATION = "continuation"
    BREAKOUT = "breakout"
    CONSOLIDATION = "consolidation"


@dataclass
class CognitivePattern:
    """Cognitive pattern"""
    id: str
    type: PatternType
    confidence: float
    strength: float
    start_time: datetime
    end_time: datetime
    features: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "confidence": self.confidence,
            "strength": self.strength,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "features": self.features,
            "metadata": self.metadata,
        }


@dataclass
class CognitiveInsight:
    """Cognitive insight"""
    id: str
    type: CognitionType
    title: str
    description: str
    confidence: float
    timestamp: datetime
    patterns: List[CognitivePattern]
    data: Dict[str, Any]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "patterns": [p.to_dict() for p in self.patterns],
            "data": self.data,
            "recommendations": self.recommendations,
        }


@dataclass
class MarketPsychology:
    """Market psychology indicators"""
    fear_greed_index: float
    market_sentiment: float
    volatility_confidence: float
    risk_appetite: float
    panic_index: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "fear_greed_index": self.fear_greed_index,
            "market_sentiment": self.market_sentiment,
            "volatility_confidence": self.volatility_confidence,
            "risk_appetite": self.risk_appetite,
            "panic_index": self.panic_index,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# DATA COGNITION ENGINE
# ============================================================

class DataCognitionEngine:
    """
    Comprehensive data cognition engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data cognition engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.random_seed = self.config.get("random_seed", 42)
        self.learning_rate = self.config.get("learning_rate", 0.01)
        
        if not HAS_SKLEARN:
            logger.warning("scikit-learn not installed. Cognitive capabilities limited.")
        
        # State
        self.patterns: List[CognitivePattern] = []
        self.insights: List[CognitiveInsight] = []
        self.psychology_history: List[MarketPsychology] = []
        self.pattern_detectors: Dict[str, Callable] = {}
        
        # Register default detectors
        self._register_default_detectors()
        
        logger.info("Data cognition engine initialized")
    
    # ============================================================
    # PATTERN DETECTORS
    # ============================================================
    
    def _register_default_detectors(self) -> None:
        """Register default pattern detectors"""
        self.register_detector("trend", self._detect_trend)
        self.register_detector("reversal", self._detect_reversal)
        self.register_detector("breakout", self._detect_breakout)
        self.register_detector("consolidation", self._detect_consolidation)
    
    def register_detector(
        self,
        name: str,
        detector: Callable[[np.ndarray], List[CognitivePattern]]
    ) -> None:
        """
        Register a pattern detector
        
        Args:
            name: Detector name
            detector: Detector function
        """
        self.pattern_detectors[name] = detector
        logger.info(f"Registered detector: {name}")
    
    # ============================================================
    # PATTERN DETECTION
    # ============================================================
    
    def detect_patterns(
        self,
        data: np.ndarray,
        detectors: Optional[List[str]] = None
    ) -> List[CognitivePattern]:
        """
        Detect patterns in data
        
        Args:
            data: Data to analyze
            detectors: Detectors to use
            
        Returns:
            List of CognitivePattern
        """
        patterns = []
        
        if detectors is None:
            detectors = list(self.pattern_detectors.keys())
        
        for detector_name in detectors:
            if detector_name in self.pattern_detectors:
                try:
                    detector = self.pattern_detectors[detector_name]
                    detected = detector(data)
                    patterns.extend(detected)
                except Exception as e:
                    logger.error(f"Detector {detector_name} failed: {e}")
        
        self.patterns.extend(patterns)
        return patterns
    
    def _detect_trend(self, data: np.ndarray) -> List[CognitivePattern]:
        """
        Detect trend patterns
        
        Args:
            data: Price data
            
        Returns:
            List of patterns
        """
        patterns = []
        
        if len(data) < 20:
            return patterns
        
        # Simple trend detection using linear regression
        x = np.arange(len(data))
        slope, intercept = np.polyfit(x, data, 1)
        
        # Calculate R-squared
        predicted = slope * x + intercept
        ss_res = np.sum((data - predicted) ** 2)
        ss_tot = np.sum((data - np.mean(data)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Determine trend type
        if slope > 0 and r_squared > 0.6:
            pattern_type = PatternType.TREND
            description = "Uptrend detected"
        elif slope < 0 and r_squared > 0.6:
            pattern_type = PatternType.TREND
            description = "Downtrend detected"
        else:
            return patterns
        
        pattern = CognitivePattern(
            id=f"pattern_{int(time.time())}_{len(patterns)}",
            type=pattern_type,
            confidence=r_squared,
            strength=abs(slope) / (np.std(data) + 0.001),
            start_time=datetime.now() - timedelta(minutes=len(data)),
            end_time=datetime.now(),
            features={
                "slope": slope,
                "intercept": intercept,
                "r_squared": r_squared,
                "description": description,
            },
        )
        
        patterns.append(pattern)
        return patterns
    
    def _detect_reversal(self, data: np.ndarray) -> List[CognitivePattern]:
        """
        Detect reversal patterns
        
        Args:
            data: Price data
            
        Returns:
            List of patterns
        """
        patterns = []
        
        if len(data) < 30:
            return patterns
        
        # Detect potential reversals using peaks and troughs
        from scipy.signal import find_peaks
        
        peaks, _ = find_peaks(data, distance=5)
        troughs, _ = find_peaks(-data, distance=5)
        
        if len(peaks) >= 3 and len(troughs) >= 2:
            # Check for double top reversal
            last_two_peaks = peaks[-2:]
            if len(last_two_peaks) == 2:
                peak_values = data[last_two_peaks]
                if abs(peak_values[0] - peak_values[1]) / peak_values[0] < 0.02:
                    # Double top detected
                    patterns.append(
                        CognitivePattern(
                            id=f"pattern_{int(time.time())}_{len(patterns)}",
                            type=PatternType.REVERSAL,
                            confidence=0.7,
                            strength=0.6,
                            start_time=datetime.now() - timedelta(minutes=len(data)),
                            end_time=datetime.now(),
                            features={
                                "type": "double_top",
                                "peak1": float(peak_values[0]),
                                "peak2": float(peak_values[1]),
                            },
                        )
                    )
        
        if len(troughs) >= 3 and len(peaks) >= 2:
            # Check for double bottom reversal
            last_two_troughs = troughs[-2:]
            if len(last_two_troughs) == 2:
                trough_values = data[last_two_troughs]
                if abs(trough_values[0] - trough_values[1]) / trough_values[0] < 0.02:
                    # Double bottom detected
                    patterns.append(
                        CognitivePattern(
                            id=f"pattern_{int(time.time())}_{len(patterns)}",
                            type=PatternType.REVERSAL,
                            confidence=0.7,
                            strength=0.6,
                            start_time=datetime.now() - timedelta(minutes=len(data)),
                            end_time=datetime.now(),
                            features={
                                "type": "double_bottom",
                                "bottom1": float(trough_values[0]),
                                "bottom2": float(trough_values[1]),
                            },
                        )
                    )
        
        return patterns
    
    def _detect_breakout(self, data: np.ndarray) -> List[CognitivePattern]:
        """
        Detect breakout patterns
        
        Args:
            data: Price data
            
        Returns:
            List of patterns
        """
        patterns = []
        
        if len(data) < 20:
            return patterns
        
        # Calculate support and resistance
        window = 10
        rolling_max = pd.Series(data).rolling(window).max()
        rolling_min = pd.Series(data).rolling(window).min()
        
        resistance = rolling_max.iloc[-1]
        support = rolling_min.iloc[-1]
        
        current_price = data[-1]
        
        # Check for breakout
        if current_price > resistance * 1.01:
            patterns.append(
                CognitivePattern(
                    id=f"pattern_{int(time.time())}_{len(patterns)}",
                    type=PatternType.BREAKOUT,
                    confidence=0.75,
                    strength=(current_price - resistance) / resistance,
                    start_time=datetime.now() - timedelta(minutes=window),
                    end_time=datetime.now(),
                    features={
                        "type": "resistance_breakout",
                        "resistance": resistance,
                        "current_price": current_price,
                        "breakout_percent": (current_price - resistance) / resistance * 100,
                    },
                )
            )
        elif current_price < support * 0.99:
            patterns.append(
                CognitivePattern(
                    id=f"pattern_{int(time.time())}_{len(patterns)}",
                    type=PatternType.BREAKOUT,
                    confidence=0.75,
                    strength=(support - current_price) / support,
                    start_time=datetime.now() - timedelta(minutes=window),
                    end_time=datetime.now(),
                    features={
                        "type": "support_breakdown",
                        "support": support,
                        "current_price": current_price,
                        "breakdown_percent": (support - current_price) / support * 100,
                    },
                )
            )
        
        return patterns
    
    def _detect_consolidation(self, data: np.ndarray) -> List[CognitivePattern]:
        """
        Detect consolidation patterns
        
        Args:
            data: Price data
            
        Returns:
            List of patterns
        """
        patterns = []
        
        if len(data) < 30:
            return patterns
        
        # Calculate volatility over recent period
        returns = np.diff(np.log(data))
        recent_volatility = np.std(returns[-10:])
        overall_volatility = np.std(returns)
        
        if recent_volatility < overall_volatility * 0.5:
            patterns.append(
                CognitivePattern(
                    id=f"pattern_{int(time.time())}_{len(patterns)}",
                    type=PatternType.CONSOLIDATION,
                    confidence=0.7,
                    strength=1 - recent_volatility / overall_volatility,
                    start_time=datetime.now() - timedelta(minutes=20),
                    end_time=datetime.now(),
                    features={
                        "recent_volatility": recent_volatility,
                        "overall_volatility": overall_volatility,
                        "volatility_reduction": (1 - recent_volatility / overall_volatility) * 100,
                    },
                )
            )
        
        return patterns
    
    # ============================================================
    # MARKET PSYCHOLOGY
    # ============================================================
    
    def analyze_market_psychology(
        self,
        price_data: np.ndarray,
        volume_data: Optional[np.ndarray] = None,
        sentiment_data: Optional[float] = None
    ) -> MarketPsychology:
        """
        Analyze market psychology
        
        Args:
            price_data: Price data
            volume_data: Volume data
            sentiment_data: Sentiment score
            
        Returns:
            MarketPsychology
        """
        # Calculate fear & greed index
        returns = np.diff(np.log(price_data))
        volatility = np.std(returns) * np.sqrt(252)
        
        # Normalize to 0-100
        fear_greed = 50 - (volatility - 0.15) * 100
        
        # Market sentiment
        if sentiment_data is not None:
            sentiment = sentiment_data
        else:
            # Calculate from price movement
            momentum = (price_data[-1] - price_data[-20]) / price_data[-20] if len(price_data) >= 20 else 0
            sentiment = 50 + momentum * 100
        
        # Volatility confidence (inverse of volatility)
        volatility_confidence = max(0, 100 - volatility * 200)
        
        # Risk appetite
        risk_appetite = (fear_greed + sentiment) / 2
        
        # Panic index
        panic = max(0, 100 - (sentiment + 50))
        
        psychology = MarketPsychology(
            fear_greed_index=max(0, min(100, fear_greed)),
            market_sentiment=max(0, min(100, sentiment)),
            volatility_confidence=max(0, min(100, volatility_confidence)),
            risk_appetite=max(0, min(100, risk_appetite)),
            panic_index=max(0, min(100, panic)),
        )
        
        self.psychology_history.append(psychology)
        return psychology
    
    # ============================================================
    # COGNITIVE REASONING
    # ============================================================
    
    def reason(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[CognitiveInsight]:
        """
        Perform cognitive reasoning on data
        
        Args:
            data: Input data
            context: Additional context
            
        Returns:
            List of CognitiveInsight
        """
        insights = []
        
        # Detect patterns
        if "price_data" in data:
            patterns = self.detect_patterns(np.array(data["price_data"]))
        else:
            patterns = []
        
        # Market psychology
        if "price_data" in data:
            psychology = self.analyze_market_psychology(
                np.array(data["price_data"]),
                data.get("volume_data"),
                data.get("sentiment"),
            )
        else:
            psychology = None
        
        # Generate insights
        if patterns:
            # Pattern insight
            pattern_insight = CognitiveInsight(
                id=f"insight_{int(time.time())}_{len(insights)}",
                type=CognitionType.PATTERN_RECOGNITION,
                title=f"Pattern Detected: {patterns[0].type.value}",
                description=f"Detected {len(patterns)} patterns in market data",
                confidence=patterns[0].confidence,
                timestamp=datetime.now(),
                patterns=patterns,
                data=data,
                recommendations=self._generate_recommendations(patterns),
            )
            insights.append(pattern_insight)
        
        if psychology:
            # Psychology insight
            psychology_insight = CognitiveInsight(
                id=f"insight_{int(time.time())}_{len(insights)}",
                type=CognitionType.PSYCHOLOGICAL_ANALYSIS,
                title="Market Psychology Analysis",
                description=f"Fear/Greed: {psychology.fear_greed_index:.1f}, Sentiment: {psychology.market_sentiment:.1f}",
                confidence=0.8,
                timestamp=datetime.now(),
                patterns=[],
                data={"psychology": psychology.to_dict()},
                recommendations=self._generate_psychology_recommendations(psychology),
            )
            insights.append(psychology_insight)
        
        self.insights.extend(insights)
        return insights
    
    def _generate_recommendations(
        self,
        patterns: List[CognitivePattern]
    ) -> List[str]:
        """
        Generate recommendations based on patterns
        
        Args:
            patterns: Detected patterns
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for pattern in patterns:
            if pattern.type == PatternType.TREND:
                if pattern.features.get("slope", 0) > 0:
                    recommendations.append("Consider following the uptrend")
                else:
                    recommendations.append("Consider following the downtrend")
            elif pattern.type == PatternType.REVERSAL:
                if "double_top" in str(pattern.features):
                    recommendations.append("Consider taking profits or reducing long positions")
                elif "double_bottom" in str(pattern.features):
                    recommendations.append("Consider entering long positions")
            elif pattern.type == PatternType.BREAKOUT:
                if "resistance_breakout" in str(pattern.features):
                    recommendations.append("Consider buying on breakout confirmation")
                else:
                    recommendations.append("Consider selling on breakdown confirmation")
            elif pattern.type == PatternType.CONSOLIDATION:
                recommendations.append("Wait for breakout direction before trading")
        
        return list(set(recommendations))
    
    def _generate_psychology_recommendations(
        self,
        psychology: MarketPsychology
    ) -> List[str]:
        """
        Generate recommendations based on psychology
        
        Args:
            psychology: Market psychology
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if psychology.fear_greed_index < 20:
            recommendations.append("Extreme fear - potential buying opportunity")
        elif psychology.fear_greed_index > 80:
            recommendations.append("Extreme greed - consider taking profits")
        
        if psychology.panic_index > 70:
            recommendations.append("High panic - consider defensive positioning")
        
        if psychology.risk_appetite < 30:
            recommendations.append("Low risk appetite - consider reducing position sizes")
        
        return recommendations
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cognition statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_patterns": len(self.patterns),
            "total_insights": len(self.insights),
            "psychology_records": len(self.psychology_history),
            "detectors": list(self.pattern_detectors.keys()),
            "last_psychology": self.psychology_history[-1].to_dict() if self.psychology_history else None,
            "pattern_types": {
                pt.value: len([p for p in self.patterns if p.type == pt])
                for pt in PatternType
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CognitionType",
    "PatternType",
    
    # Dataclasses
    "CognitivePattern",
    "CognitiveInsight",
    "MarketPsychology",
    
    # Classes
    "DataCognitionEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

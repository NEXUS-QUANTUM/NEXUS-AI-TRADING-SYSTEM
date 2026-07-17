"""
NEXUS AI TRADING SYSTEM - Custom Indicators for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/indicators/custom_indicators.py
Description: Indicateurs techniques personnalisés pour le bot AI.
             Implémente des indicateurs avancés et propriétaires:
             - Indicateurs de sentiment de marché
             - Indicateurs de microstructure
             - Indicateurs de flux d'ordres
             - Indicateurs de régime de marché
             - Indicateurs de volatilité adaptative
             - Indicateurs de corrélation croisée
             - Indicateurs de cycle de marché
             - Indicateurs de force relative avancés
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks, hilbert
from scipy.fft import fft, ifft, rfft, irfft
from scipy.stats import entropy, pearsonr, spearmanr
from scipy.ndimage import gaussian_filter1d

from trading.bots.ai_bot.indicators.base_indicator import (
    BaseIndicator,
    IndicatorConfig,
    IndicatorResult,
    IndicatorCategory,
    IndicatorType
)
from shared.helpers.number_helpers import round_decimal
from shared.exceptions import IndicatorError

# Configuration du logging
logger = logging.getLogger(__name__)


# ============================================================
# INDICATEUR DE SENTIMENT DE MARCHÉ
# ============================================================

class MarketSentimentIndicator(BaseIndicator):
    """
    Indicateur de sentiment de marché.
    Combine plusieurs métriques pour évaluer le sentiment global.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'sentiment_period': 14,
            'volatility_weight': 0.3,
            'momentum_weight': 0.3,
            'volume_weight': 0.2,
            'breadth_weight': 0.2,
            'threshold_overbought': 0.7,
            'threshold_oversold': 0.3
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule le sentiment de marché.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        volume = data['volume']
        high = data['high']
        low = data['low']
        period = p['sentiment_period']
        
        # 1. Momentum (RSI normalisé)
        rsi = self._calculate_rsi(close, period)
        momentum_score = rsi / 100
        
        # 2. Volatilité (ATR normalisé)
        atr = self._calculate_atr(high, low, close, period)
        max_atr = atr.rolling(period * 2).max()
        volatility_score = atr / max_atr
        volatility_score = volatility_score.fillna(0.5)
        
        # 3. Volume (OBV normalisé)
        obv = self._calculate_obv(close, volume)
        obv_normalized = (obv - obv.rolling(period).min()) / (obv.rolling(period).max() - obv.rolling(period).min())
        volume_score = obv_normalized.fillna(0.5)
        
        # 4. Breadth (pourcentage de gains)
        returns = close.pct_change()
        gains = (returns > 0).rolling(period).sum() / period
        breadth_score = gains
        
        # Score composite
        sentiment = (
            p['momentum_weight'] * momentum_score +
            p['volatility_weight'] * (1 - volatility_score) +
            p['volume_weight'] * volume_score +
            p['breadth_weight'] * breadth_score
        )
        
        # Normalisation
        sentiment = sentiment.clip(0, 1)
        
        # Signal
        signal = pd.Series(0, index=close.index)
        signal[sentiment > p['threshold_overbought']] = 1  # Sur-achat
        signal[sentiment < p['threshold_oversold']] = -1  # Sur-vente
        
        result = IndicatorResult(
            values=sentiment,
            timestamp=data['timestamp'],
            name="MarketSentiment",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        # Ajout du signal comme attribut
        result.signal = signal
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)
    
    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Calcule le RSI."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calcule l'ATR."""
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calculate_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calcule l'OBV."""
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        return obv


# ============================================================
# INDICATEUR DE FLUX D'ORDRES
# ============================================================

class OrderFlowIndicator(BaseIndicator):
    """
    Indicateur de flux d'ordres.
    Analyse le déséquilibre entre ordres d'achat et de vente.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'period': 14,
            'smooth': True,
            'smooth_period': 5,
            'threshold': 0.3
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule le flux d'ordres.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        high = data['high']
        low = data['low']
        volume = data['volume']
        
        # Calcul du flux d'ordres
        # Utilisation de la méthode de déséquilibre de volume
        typical_price = (high + low + close) / 3
        volume_delta = volume * (close - low - (high - close)) / (high - low + 1e-8)
        
        # Cumul
        cumulative_flow = volume_delta.rolling(p['period']).sum()
        
        # Normalisation
        max_flow = cumulative_flow.abs().rolling(p['period'] * 2).max()
        flow = cumulative_flow / max_flow
        flow = flow.clip(-1, 1).fillna(0)
        
        # Lissage
        if p['smooth']:
            flow = flow.rolling(p['smooth_period']).mean()
        
        # Signal
        signal = pd.Series(0, index=close.index)
        signal[flow > p['threshold']] = 1  # Pression acheteuse
        signal[flow < -p['threshold']] = -1  # Pression vendeuse
        
        result = IndicatorResult(
            values=flow,
            timestamp=data['timestamp'],
            name="OrderFlow",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        result.signal = signal
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)


# ============================================================
# INDICATEUR DE RÉGIME DE MARCHÉ
# ============================================================

class MarketRegimeIndicator(BaseIndicator):
    """
    Indicateur de régime de marché.
    Identifie les régimes: tendance, range, volatil, calme.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'trend_period': 20,
            'volatility_period': 20,
            'threshold_trend': 0.02,
            'threshold_volatility': 0.01,
            'regime_labels': ['range', 'trend_up', 'trend_down', 'volatile']
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule le régime de marché.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        high = data['high']
        low = data['low']
        
        # 1. Force de la tendance (ADX)
        adx = self._calculate_adx(high, low, close, p['trend_period'])
        trend_strength = adx / 100
        
        # 2. Direction de la tendance
        sma = close.rolling(p['trend_period']).mean()
        trend_direction = (close > sma).astype(int) * 2 - 1  # -1 ou 1
        
        # 3. Volatilité
        atr = self._calculate_atr(high, low, close, p['volatility_period'])
        volatility = atr / close
        
        # Normalisation
        max_vol = volatility.rolling(p['volatility_period'] * 2).max()
        volatility_norm = volatility / max_vol
        
        # Régime
        regimes = pd.Series(0, index=close.index)
        
        # Tendance haussière
        regimes[(trend_strength > p['threshold_trend']) & (trend_direction > 0)] = 1
        # Tendance baissière
        regimes[(trend_strength > p['threshold_trend']) & (trend_direction < 0)] = -1
        # Volatil
        regimes[volatility_norm > p['threshold_volatility']] = 2
        # Range (par défaut)
        regimes[regimes == 0] = 0
        
        result = IndicatorResult(
            values=regimes,
            timestamp=data['timestamp'],
            name="MarketRegime",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        # Ajout des métriques
        result.trend_strength = trend_strength
        result.volatility = volatility_norm
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calcule l'ADX."""
        atr = self._calculate_atr(high, low, close, period)
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(period).mean().fillna(0)
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calcule l'ATR."""
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()


# ============================================================
# INDICATEUR DE CORRÉLATION CROISÉE
# ============================================================

class CrossCorrelationIndicator(BaseIndicator):
    """
    Indicateur de corrélation croisée entre actifs.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'period': 20,
            'reference_symbol': 'SPY',
            'window': 10,
            'threshold': 0.7
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule la corrélation croisée.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        returns = close.pct_change()
        
        # Simulation de corrélation avec un actif de référence
        # Dans la pratique, utiliser les données du marché réel
        reference_returns = np.random.normal(0, 0.01, len(returns)) * 0.5 + returns * 0.5
        
        # Corrélation glissante
        correlation = returns.rolling(p['period']).corr(pd.Series(reference_returns, index=returns.index))
        correlation = correlation.fillna(0)
        
        # Signal
        signal = pd.Series(0, index=close.index)
        signal[correlation > p['threshold']] = 1
        signal[correlation < -p['threshold']] = -1
        
        result = IndicatorResult(
            values=correlation,
            timestamp=data['timestamp'],
            name="CrossCorrelation",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        result.signal = signal
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)


# ============================================================
# INDICATEUR DE VOLATILITÉ ADAPTATIVE
# ============================================================

class AdaptiveVolatilityIndicator(BaseIndicator):
    """
    Indicateur de volatilité adaptative.
    S'ajuste aux conditions de marché changeantes.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'base_period': 14,
            'adaptation_factor': 0.5,
            'max_period': 50,
            'min_period': 5,
            'outlier_threshold': 3.0
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule la volatilité adaptative.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        returns = close.pct_change()
        
        # Volatilité de base
        base_volatility = returns.rolling(p['base_period']).std()
        
        # Détection des changements de régime
        volatility_change = base_volatility.pct_change().abs()
        
        # Période adaptative
        adaptive_period = p['base_period'] * (1 + p['adaptation_factor'] * volatility_change)
        adaptive_period = adaptive_period.clip(p['min_period'], p['max_period'])
        adaptive_period = adaptive_period.round().astype(int)
        
        # Volatilité adaptative
        adaptive_volatility = pd.Series(index=close.index, dtype=float)
        
        for i in range(adaptive_period.max(), len(returns)):
            period = max(2, int(adaptive_period.iloc[i]))
            start = max(0, i - period)
            adaptive_volatility.iloc[i] = returns.iloc[start:i].std()
        
        adaptive_volatility = adaptive_volatility.fillna(base_volatility)
        
        # Détection des outliers
        z_scores = np.abs(stats.zscore(adaptive_volatility.dropna()))
        outlier_mask = z_scores > p['outlier_threshold']
        
        # Signal de régime de volatilité
        volatility_regime = pd.Series(0, index=close.index)
        volatility_regime[adaptive_volatility > adaptive_volatility.rolling(50).mean() * 1.5] = 1  # Haute volatilité
        volatility_regime[adaptive_volatility < adaptive_volatility.rolling(50).mean() * 0.5] = -1  # Basse volatilité
        
        result = IndicatorResult(
            values=adaptive_volatility,
            timestamp=data['timestamp'],
            name="AdaptiveVolatility",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        result.outlier_mask = outlier_mask
        result.volatility_regime = volatility_regime
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)


# ============================================================
# INDICATEUR DE CYCLE DE MARCHÉ
# ============================================================

class MarketCycleIndicator(BaseIndicator):
    """
    Indicateur de cycle de marché.
    Utilise l'analyse de Fourier pour identifier les cycles.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'cycle_periods': [10, 20, 40, 80],
            'dominant_cycle': 20,
            'smooth_factor': 0.5,
            'threshold': 0.3
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule le cycle de marché.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        n = len(close)
        
        # Détrendage
        trend = close.rolling(200).mean().fillna(close.mean())
        detrended = close - trend
        
        # Transformée de Fourier
        fft_vals = fft(detrended.values)
        
        # Identification du cycle dominant
        freqs = np.fft.fftfreq(n)
        power = np.abs(fft_vals) ** 2
        
        # Masque pour les fréquences positives
        positive_mask = freqs > 0
        
        # Recherche des pics de puissance
        power_pos = power[positive_mask]
        freqs_pos = freqs[positive_mask]
        
        # Périodes correspondantes
        if len(power_pos) > 0:
            dominant_freq_idx = np.argmax(power_pos)
            dominant_freq = freqs_pos[dominant_freq_idx]
            dominant_period = int(1 / dominant_freq) if dominant_freq > 0 else p['dominant_cycle']
        else:
            dominant_period = p['dominant_cycle']
        
        # Reconstruction du cycle dominant
        cycle = np.zeros(n)
        for period in p['cycle_periods']:
            freq = 1 / period
            idx = int(freq * n)
            if idx < n // 2:
                cycle += np.real(fft_vals[idx] * np.exp(2j * np.pi * freq * np.arange(n)))
        
        # Normalisation
        cycle_norm = (cycle - np.mean(cycle)) / (np.std(cycle) + 1e-8)
        cycle_norm = np.clip(cycle_norm, -1, 1)
        
        # Signal de phase du cycle
        phase = np.arctan2(np.imag(fft_vals), np.real(fft_vals))
        phase = pd.Series(phase[:n], index=close.index)
        
        # Signal de cycle
        cycle_signal = pd.Series(0, index=close.index)
        cycle_signal[cycle_norm > p['threshold']] = 1  # Phase haute
        cycle_signal[cycle_norm < -p['threshold']] = -1  # Phase basse
        
        result = IndicatorResult(
            values=pd.Series(cycle_norm, index=close.index),
            timestamp=data['timestamp'],
            name="MarketCycle",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        result.phase = phase
        result.dominant_period = dominant_period
        result.cycle_signal = cycle_signal
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)


# ============================================================
# INDICATEUR DE FORCE RELATIVE AVANCÉ (ARV)
# ============================================================

class AdvancedRSIIndicator(BaseIndicator):
    """
    Indicateur de force relative avancé.
    Version améliorée du RSI avec adaptabilité et signaux.
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            'period': 14,
            'smooth_period': 3,
            'overbought': 70,
            'oversold': 30,
            'divergence_window': 5,
            'adaptive': True
        }
    
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule le RSI avancé.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        if not self.validate_data(data):
            raise IndicatorError("Données invalides")
        
        p = {**self.get_default_params(), **(params or {})}
        
        close = data['close']
        
        # RSI de base
        rsi = self._calculate_rsi(close, p['period'])
        
        # Lissage
        if p['smooth_period'] > 1:
            rsi = rsi.rolling(p['smooth_period']).mean()
        
        # RSI adaptatif
        if p['adaptive']:
            volatility = close.pct_change().rolling(p['period']).std()
            adaptation = volatility / volatility.rolling(p['period'] * 2).mean()
            rsi = rsi * (1 + 0.1 * adaptation)
            rsi = rsi.clip(0, 100)
        
        # Détection de divergences
        divergences = pd.Series(0, index=close.index)
        
        for i in range(p['divergence_window'] * 2, len(close)):
            # Divergence haussière (prix plus bas, RSI plus haut)
            if close.iloc[i] < close.iloc[i - p['divergence_window']]:
                if rsi.iloc[i] > rsi.iloc[i - p['divergence_window']]:
                    divergences.iloc[i] = 1
            
            # Divergence baissière (prix plus haut, RSI plus bas)
            if close.iloc[i] > close.iloc[i - p['divergence_window']]:
                if rsi.iloc[i] < rsi.iloc[i - p['divergence_window']]:
                    divergences.iloc[i] = -1
        
        result = IndicatorResult(
            values=rsi,
            timestamp=data['timestamp'],
            name="AdvancedRSI",
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            params=p
        )
        
        result.divergences = divergences
        result.overbought = p['overbought']
        result.oversold = p['oversold']
        
        return result
    
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """Met à jour l'indicateur."""
        if self.state.data is None:
            self.state.data = new_data
        else:
            self.state.data = self._merge_data(self.state.data, new_data)
        
        return self.calculate(self.state.data)
    
    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Calcule le RSI."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)


# ============================================================
# FABRIQUE D'INDICATEURS PERSONNALISÉS
# ============================================================

class CustomIndicatorFactory:
    """
    Fabrique d'indicateurs personnalisés.
    """
    
    _indicators = {
        'market_sentiment': MarketSentimentIndicator,
        'order_flow': OrderFlowIndicator,
        'market_regime': MarketRegimeIndicator,
        'cross_correlation': CrossCorrelationIndicator,
        'adaptive_volatility': AdaptiveVolatilityIndicator,
        'market_cycle': MarketCycleIndicator,
        'advanced_rsi': AdvancedRSIIndicator
    }
    
    @classmethod
    def create(
        cls,
        name: str,
        symbol: str,
        timeframe: str = "1h",
        **kwargs
    ) -> BaseIndicator:
        """
        Crée un indicateur personnalisé.
        
        Args:
            name: Nom de l'indicateur.
            symbol: Symbole.
            timeframe: Timeframe.
            **kwargs: Paramètres supplémentaires.
            
        Returns:
            Instance de l'indicateur.
        """
        if name not in cls._indicators:
            raise IndicatorError(f"Indicateur inconnu: {name}")
        
        config = IndicatorConfig(
            name=name,
            symbol=symbol,
            timeframe=timeframe,
            params=kwargs
        )
        
        return cls._indicators[name](config)
    
    @classmethod
    def register(cls, name: str, indicator_class: type) -> None:
        """
        Enregistre un nouvel indicateur.
        
        Args:
            name: Nom de l'indicateur.
            indicator_class: Classe de l'indicateur.
        """
        cls._indicators[name] = indicator_class
        logger.info(f"Indicateur enregistré: {name}")
    
    @classmethod
    def get_available(cls) -> List[str]:
        """Retourne la liste des indicateurs disponibles."""
        return list(cls._indicators.keys())


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    # Indicateurs
    'MarketSentimentIndicator',
    'OrderFlowIndicator',
    'MarketRegimeIndicator',
    'CrossCorrelationIndicator',
    'AdaptiveVolatilityIndicator',
    'MarketCycleIndicator',
    'AdvancedRSIIndicator',
    
    # Fabrique
    'CustomIndicatorFactory'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

"""
Swing Bot Wavelet Model
========================

This module provides wavelet analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import pywt
from scipy import signal
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class WaveletDecomposition:
    """Wavelet decomposition data structure."""
    level: int
    coefficients: List[np.ndarray]
    approximation: np.ndarray
    details: List[np.ndarray]
    frequencies: List[float]
    timestamps: List[datetime]


@dataclass
class WaveletAnalysis:
    """Wavelet analysis results."""
    decomposition: WaveletDecomposition
    energy_distribution: Dict[str, float]
    dominant_frequencies: List[float]
    trend_component: np.ndarray
    noise_component: np.ndarray
    cycle_component: np.ndarray


@dataclass
class WaveletSignal:
    """Wavelet trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    frequency_band: str
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class WaveletModel:
    """
    Wavelet analysis model for time series decomposition.
    
    Provides multi-resolution analysis of price data using wavelet transforms.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the wavelet model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.wavelet_type = self.config.get('wavelet_type', 'db4')
        self.max_level = self.config.get('max_level', 6)
        self.sampling_frequency = self.config.get('sampling_frequency', 1.0)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, data: Union[pd.Series, np.ndarray, List[float]]) -> Dict[str, Any]:
        """
        Perform wavelet analysis on time series data.
        
        Args:
            data: Time series data
            
        Returns:
            Wavelet analysis results
        """
        if isinstance(data, pd.Series):
            timestamps = data.index
            values = data.values
        elif isinstance(data, list):
            timestamps = [datetime.now() + pd.Timedelta(seconds=i) for i in range(len(data))]
            values = np.array(data)
        else:
            timestamps = [datetime.now() + pd.Timedelta(seconds=i) for i in range(len(data))]
            values = data
        
        # Perform wavelet decomposition
        decomp = self._wavelet_decomposition(values)
        
        # Analyze components
        energy_dist = self._calculate_energy_distribution(decomp)
        dominant_freqs = self._find_dominant_frequencies(decomp)
        
        # Extract components
        trend, noise, cycles = self._extract_components(decomp)
        
        # Generate signals
        signals = self._generate_signals(values, decomp, timestamps)
        
        return {
            'decomposition': decomp,
            'energy_distribution': energy_dist,
            'dominant_frequencies': dominant_freqs,
            'trend_component': trend,
            'noise_component': noise,
            'cycle_component': cycles,
            'signals': signals
        }
    
    def _wavelet_decomposition(self, data: np.ndarray) -> WaveletDecomposition:
        """
        Perform wavelet decomposition.
        
        Args:
            data: Input data
            
        Returns:
            WaveletDecomposition object
        """
        # Determine maximum decomposition level
        max_level = min(self.max_level, pywt.dwt_max_level(len(data), self.wavelet_type))
        
        # Perform decomposition
        coeffs = pywt.wavedec(data, self.wavelet_type, level=max_level)
        
        # Extract approximation and details
        approximation = coeffs[0]
        details = coeffs[1:]
        
        # Calculate frequencies
        frequencies = self._calculate_frequencies(len(data), max_level)
        
        return WaveletDecomposition(
            level=max_level,
            coefficients=coeffs,
            approximation=approximation,
            details=details,
            frequencies=frequencies,
            timestamps=[]  # Will be set later
        )
    
    def _calculate_frequencies(self, data_length: int, max_level: int) -> List[float]:
        """
        Calculate frequency bands for each decomposition level.
        
        Args:
            data_length: Length of data
            max_level: Maximum decomposition level
            
        Returns:
            List of frequency bands
        """
        nyquist = self.sampling_frequency / 2
        frequencies = []
        
        for i in range(max_level):
            freq_high = nyquist / (2 ** i)
            freq_low = nyquist / (2 ** (i + 1))
            frequencies.append((freq_low, freq_high))
        
        return frequencies
    
    def _calculate_energy_distribution(self, decomp: WaveletDecomposition) -> Dict[str, float]:
        """
        Calculate energy distribution across decomposition levels.
        
        Args:
            decomp: Wavelet decomposition
            
        Returns:
            Energy distribution dictionary
        """
        total_energy = 0
        energies = {}
        
        # Approximation energy
        approx_energy = np.sum(decomp.approximation ** 2)
        energies['approximation'] = approx_energy
        total_energy += approx_energy
        
        # Detail energies
        for i, detail in enumerate(decomp.details):
            detail_energy = np.sum(detail ** 2)
            energies[f'detail_{i+1}'] = detail_energy
            total_energy += detail_energy
        
        # Normalize
        if total_energy > 0:
            for key in energies:
                energies[key] /= total_energy
        
        return energies
    
    def _find_dominant_frequencies(self, decomp: WaveletDecomposition) -> List[float]:
        """
        Find dominant frequencies in the signal.
        
        Args:
            decomp: Wavelet decomposition
            
        Returns:
            List of dominant frequencies
        """
        dominant_freqs = []
        
        for i, detail in enumerate(decomp.details):
            if len(detail) > 0:
                # Calculate power spectrum
                f, Pxx = signal.periodogram(detail, self.sampling_frequency)
                
                # Find dominant frequency
                if len(Pxx) > 0:
                    dominant_idx = np.argmax(Pxx)
                    if dominant_idx < len(f):
                        dominant_freqs.append(f[dominant_idx])
        
        return dominant_freqs
    
    def _extract_components(self, decomp: WaveletDecomposition) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract trend, noise, and cycle components.
        
        Args:
            decomp: Wavelet decomposition
            
        Returns:
            Tuple of (trend, noise, cycle) components
        """
        # Trend is the approximation component
        trend = decomp.approximation
        
        # Noise is high-frequency details (first 1-2 levels)
        noise = np.zeros_like(decomp.coefficients[0])
        for i in range(min(2, len(decomp.details))):
            if len(decomp.details[i]) > 0:
                # Interpolate to match trend length
                detail_interp = np.interp(
                    np.linspace(0, 1, len(noise)),
                    np.linspace(0, 1, len(decomp.details[i])),
                    decomp.details[i]
                )
                noise += detail_interp
        
        # Cycles are mid-frequency details (remaining levels)
        cycles = np.zeros_like(decomp.coefficients[0])
        for i in range(2, len(decomp.details)):
            if len(decomp.details[i]) > 0:
                detail_interp = np.interp(
                    np.linspace(0, 1, len(cycles)),
                    np.linspace(0, 1, len(decomp.details[i])),
                    decomp.details[i]
                )
                cycles += detail_interp
        
        return trend, noise, cycles
    
    def _generate_signals(self, data: np.ndarray, decomp: WaveletDecomposition,
                         timestamps: List[datetime]) -> List[WaveletSignal]:
        """
        Generate trading signals from wavelet analysis.
        
        Args:
            data: Original data
            decomp: Wavelet decomposition
            timestamps: Time indices
            
        Returns:
            List of WaveletSignal objects
        """
        signals = []
        
        # Reconstruct signal from components
        reconstructed = pywt.waverec(decomp.coefficients, self.wavelet_type)
        
        # Trim to match original length
        reconstructed = reconstructed[:len(data)]
        
        # Calculate error between original and reconstructed
        error = data - reconstructed
        
        # Generate signals based on reconstruction error
        for i in range(len(error)):
            if abs(error[i]) > self.confidence_threshold * np.std(error):
                if error[i] > 0:
                    signal_type = 'buy'
                    reason = f"Positive wavelet reconstruction error at {i}"
                else:
                    signal_type = 'sell'
                    reason = f"Negative wavelet reconstruction error at {i}"
                
                signal = WaveletSignal(
                    symbol='',  # Will be set by caller
                    timestamp=timestamps[i] if i < len(timestamps) else datetime.now(),
                    signal_type=signal_type,
                    confidence=abs(error[i]) / np.std(error),
                    price=data[i] if i < len(data) else 0,
                    frequency_band=self._get_frequency_band(i, decomp),
                    reason=reason,
                    indicators={
                        'reconstruction_error': error[i],
                        'trend_component': decomp.approximation[i] if i < len(decomp.approximation) else 0,
                        'energy_distribution': self._calculate_energy_distribution(decomp)
                    }
                )
                signals.append(signal)
        
        return signals
    
    def _get_frequency_band(self, index: int, decomp: WaveletDecomposition) -> str:
        """
        Get frequency band for a given index.
        
        Args:
            index: Data index
            decomp: Wavelet decomposition
            
        Returns:
            Frequency band name
        """
        if index < len(decomp.approximation):
            return 'trend'
        
        detail_index = index - len(decomp.approximation)
        if detail_index < len(decomp.details):
            return f'detail_{detail_index + 1}'
        
        return 'unknown'
    
    def denoise(self, data: Union[pd.Series, np.ndarray, List[float]]) -> np.ndarray:
        """
        Denoise time series data using wavelet thresholding.
        
        Args:
            data: Input data
            
        Returns:
            Denoised data
        """
        if isinstance(data, (pd.Series, list)):
            data = np.array(data)
        
        # Perform decomposition
        coeffs = pywt.wavedec(data, self.wavelet_type, level=self.max_level)
        
        # Apply thresholding
        threshold = self.config.get('denoise_threshold', 0.1)
        coeffs = [pywt.threshold(c, threshold * np.std(c), mode='soft') for c in coeffs]
        
        # Reconstruct
        denoised = pywt.waverec(coeffs, self.wavelet_type)
        
        return denoised[:len(data)]
    
    def get_multiscale_features(self, data: Union[pd.Series, np.ndarray, List[float]]) -> Dict[str, Any]:
        """
        Extract multiscale features from data.
        
        Args:
            data: Input data
            
        Returns:
            Dictionary of multiscale features
        """
        if isinstance(data, (pd.Series, list)):
            data = np.array(data)
        
        features = {}
        
        # Perform decomposition at multiple levels
        for level in range(1, min(self.max_level + 1, 5)):
            coeffs = pywt.wavedec(data, self.wavelet_type, level=level)
            
            # Calculate features for each level
            for i, coeff in enumerate(coeffs):
                if len(coeff) > 0:
                    features[f'level_{level}_coeff_{i}_mean'] = np.mean(coeff)
                    features[f'level_{level}_coeff_{i}_std'] = np.std(coeff)
                    features[f'level_{level}_coeff_{i}_energy'] = np.sum(coeff ** 2)
        
        return features
    
    def detect_anomalies(self, data: Union[pd.Series, np.ndarray, List[float]],
                        threshold: float = 3.0) -> List[int]:
        """
        Detect anomalies using wavelet analysis.
        
        Args:
            data: Input data
            threshold: Anomaly threshold in standard deviations
            
        Returns:
            List of anomaly indices
        """
        if isinstance(data, (pd.Series, list)):
            data = np.array(data)
        
        # Denoise the data
        denoised = self.denoise(data)
        
        # Calculate reconstruction error
        error = data - denoised
        
        # Find anomalies
        error_std = np.std(error)
        anomalies = np.where(np.abs(error) > threshold * error_std)[0]
        
        return anomalies.tolist()
    
    def get_wavelet_energy_ratio(self, data: Union[pd.Series, np.ndarray, List[float]]) -> float:
        """
        Calculate ratio of high-frequency to low-frequency energy.
        
        Args:
            data: Input data
            
        Returns:
            Energy ratio
        """
        if isinstance(data, (pd.Series, list)):
            data = np.array(data)
        
        # Perform decomposition
        coeffs = pywt.wavedec(data, self.wavelet_type, level=self.max_level)
        
        # Calculate energies
        approx_energy = np.sum(coeffs[0] ** 2)
        total_energy = approx_energy
        
        for coeff in coeffs[1:]:
            total_energy += np.sum(coeff ** 2)
        
        if total_energy == 0:
            return 0.0
        
        return approx_energy / total_energy


def create_wavelet_model(config: Optional[Dict[str, Any]] = None) -> WaveletModel:
    """
    Create a wavelet model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        WaveletModel instance
    """
    return WaveletModel(config)


__all__ = [
    'WaveletDecomposition',
    'WaveletAnalysis',
    'WaveletSignal',
    'WaveletModel',
    'create_wavelet_model'
]

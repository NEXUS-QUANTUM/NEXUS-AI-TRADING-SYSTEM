"""
NEXUS AI TRADING SYSTEM - Data Processor for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_processor.py
Description: Processeur de données avancé pour l'extraction de features
             et la transformation de données financières. Supporte:
             - Indicateurs techniques (TA-Lib intégré)
             - Features statistiques (rolling, expanding, etc.)
             - Features de marché (order book, microstructure)
             - Features de sentiment (social, news)
             - Features macroéconomiques
             - Optimisation GPU (CUDA)
"""

import logging
import math
import warnings
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks
from scipy.fft import fft, ifft

# TA-Lib (optionnel)
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    talib = None

# GPU (optionnel)
try:
    import cupy as cp
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False
    cp = None

from shared.exceptions import ProcessingError
from shared.helpers.number_helpers import round_decimal
from shared.constants.trading_constants import INDICATORS

# Configuration du logging
logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Mode de traitement."""
    CPU = "cpu"
    GPU = "gpu"
    AUTO = "auto"


class FeatureCategory(Enum):
    """Catégories de features."""
    TECHNICAL = "technical"
    STATISTICAL = "statistical"
    MARKET = "market"
    SENTIMENT = "sentiment"
    MACRO = "macro"
    DERIVED = "derived"
    CUSTOM = "custom"


@dataclass
class ProcessingConfig:
    """
    Configuration du processeur de données.
    """
    # Mode de traitement
    mode: ProcessingMode = ProcessingMode.AUTO
    use_talib: bool = True
    
    # Features techniques
    enable_technical: bool = True
    technical_indicators: List[str] = field(default_factory=lambda: [
        'sma', 'ema', 'rsi', 'macd', 'bbands', 'atr',
        'stoch', 'adx', 'cci', 'willr', 'roc', 'mom'
    ])
    
    # Features statistiques
    enable_statistical: bool = True
    statistical_window: int = 14
    statistical_features: List[str] = field(default_factory=lambda: [
        'mean', 'std', 'skew', 'kurt', 'quantile',
        'rolling_corr', 'rolling_cov', 'zscore'
    ])
    
    # Features de marché
    enable_market: bool = True
    market_features: List[str] = field(default_factory=lambda: [
        'bid_ask_spread', 'order_book_imbalance',
        'market_depth', 'liquidity', 'volatility'
    ])
    
    # Features de sentiment
    enable_sentiment: bool = False
    sentiment_sources: List[str] = field(default_factory=lambda: [
        'twitter', 'news', 'reddit', 'telegram'
    ])
    
    # Paramètres d'optimisation
    batch_size: int = 1000
    parallel: bool = True
    n_jobs: int = 4
    use_cache: bool = True
    cache_ttl: int = 3600
    
    # Paramètres de sortie
    output_dtype: str = "float32"
    normalize_output: bool = False
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.batch_size < 1:
            raise ProcessingError("batch_size doit être >= 1")
        
        if self.n_jobs < 1:
            raise ProcessingError("n_jobs doit être >= 1")
        
        # Vérification de TA-Lib
        if self.use_talib and not TALIB_AVAILABLE:
            logger.warning("TA-Lib non disponible, désactivation")
            self.use_talib = False
        
        # Mode GPU
        if self.mode == ProcessingMode.GPU and not CUDA_AVAILABLE:
            logger.warning("CUDA non disponible, passage en mode CPU")
            self.mode = ProcessingMode.CPU


@dataclass
class FeatureSet:
    """
    Ensemble de features.
    """
    name: str
    category: FeatureCategory
    features: pd.DataFrame
    created_at: datetime = field(default_factory=datetime.now)
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'name': self.name,
            'category': self.category.value,
            'shape': self.features.shape,
            'columns': list(self.features.columns),
            'created_at': self.created_at.isoformat(),
            'processing_time': self.processing_time
        }


class DataProcessor:
    """
    Processeur de données pour l'extraction de features.
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        """
        Initialise le processeur de données.
        
        Args:
            config: Configuration du processeur.
        """
        self.config = config or ProcessingConfig()
        
        # Mode de traitement
        self._use_gpu = self._detect_gpu_mode()
        
        # Cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            'total_processed': 0,
            'total_features': 0,
            'processing_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info(f"DataProcessor initialisé - Mode: {self.config.mode.value}")
        logger.info(f"GPU: {self._use_gpu}")
        logger.info(f"TA-Lib: {self.config.use_talib}")
    
    def _detect_gpu_mode(self) -> bool:
        """
        Détecte si le mode GPU doit être utilisé.
        
        Returns:
            True si GPU disponible.
        """
        if self.config.mode == ProcessingMode.GPU:
            return CUDA_AVAILABLE
        elif self.config.mode == ProcessingMode.AUTO:
            return CUDA_AVAILABLE and self.config.batch_size > 1000
        return False
    
    def _to_array(self, data: Union[np.ndarray, pd.DataFrame, List]) -> np.ndarray:
        """
        Convertit les données en array numpy.
        
        Args:
            data: Données à convertir.
            
        Returns:
            Array numpy.
        """
        if isinstance(data, pd.DataFrame):
            return data.values
        elif isinstance(data, list):
            return np.array(data)
        return data
    
    # ============================================================
    # INDICATEURS TECHNIQUES
    # ============================================================
    
    def add_technical_indicators(
        self,
        data: pd.DataFrame,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Ajoute des indicateurs techniques au DataFrame.
        
        Args:
            data: DataFrame OHLCV.
            indicators: Liste des indicateurs à ajouter.
            
        Returns:
            DataFrame avec indicateurs.
        """
        if not self.config.enable_technical:
            return data
        
        if indicators is None:
            indicators = self.config.technical_indicators
        
        logger.info(f"Ajout de {len(indicators)} indicateurs techniques")
        
        df = data.copy()
        
        for indicator in indicators:
            try:
                if indicator.lower() == 'sma':
                    df['sma'] = self._sma(df['close'])
                elif indicator.lower() == 'ema':
                    df['ema'] = self._ema(df['close'])
                elif indicator.lower() == 'rsi':
                    df['rsi'] = self._rsi(df['close'])
                elif indicator.lower() == 'macd':
                    macd, signal, hist = self._macd(df['close'])
                    df['macd'] = macd
                    df['macd_signal'] = signal
                    df['macd_hist'] = hist
                elif indicator.lower() == 'bbands':
                    upper, middle, lower = self._bbands(df['close'])
                    df['bb_upper'] = upper
                    df['bb_middle'] = middle
                    df['bb_lower'] = lower
                elif indicator.lower() == 'atr':
                    df['atr'] = self._atr(df['high'], df['low'], df['close'])
                elif indicator.lower() == 'stoch':
                    slowk, slowd = self._stoch(df['high'], df['low'], df['close'])
                    df['stoch_k'] = slowk
                    df['stoch_d'] = slowd
                elif indicator.lower() == 'adx':
                    df['adx'] = self._adx(df['high'], df['low'], df['close'])
                elif indicator.lower() == 'cci':
                    df['cci'] = self._cci(df['high'], df['low'], df['close'])
                elif indicator.lower() == 'willr':
                    df['willr'] = self._willr(df['high'], df['low'], df['close'])
                elif indicator.lower() == 'roc':
                    df['roc'] = self._roc(df['close'])
                elif indicator.lower() == 'mom':
                    df['mom'] = self._mom(df['close'])
                elif indicator.lower() == 'bollinger_width':
                    df['bb_width'] = df['bb_upper'] - df['bb_lower']
                elif indicator.lower() == 'bollinger_%b':
                    df['bb_%b'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
                elif indicator.lower() == 'obv':
                    df['obv'] = self._obv(df['close'], df['volume'])
                elif indicator.lower() == 'vwap':
                    df['vwap'] = self._vwap(df['close'], df['volume'])
                elif indicator.lower() == 'ichimoku':
                    df = self._ichimoku(df)
                else:
                    logger.warning(f"Indicateur non supporté: {indicator}")
                
            except Exception as e:
                logger.error(f"Erreur {indicator}: {e}")
                continue
        
        return df
    
    def _sma(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Simple Moving Average."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.SMA(close, timeperiod=period), index=close.index)
        return close.rolling(window=period).mean()
    
    def _ema(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Exponential Moving Average."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.EMA(close, timeperiod=period), index=close.index)
        return close.ewm(span=period, adjust=False).mean()
    
    def _rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.RSI(close, timeperiod=period), index=close.index)
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD."""
        if self.config.use_talib and TALIB_AVAILABLE:
            macd, signal_line, hist = talib.MACD(close, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            return pd.Series(macd, index=close.index), pd.Series(signal_line, index=close.index), pd.Series(hist, index=close.index)
        
        ema_fast = self._ema(close, fast)
        ema_slow = self._ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return macd_line, signal_line, hist
    
    def _bbands(self, close: pd.Series, period: int = 20, nbdevup: int = 2, nbdevdn: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands."""
        if self.config.use_talib and TALIB_AVAILABLE:
            upper, middle, lower = talib.BBANDS(close, timeperiod=period, nbdevup=nbdevup, nbdevdn=nbdevdn)
            return pd.Series(upper, index=close.index), pd.Series(middle, index=close.index), pd.Series(lower, index=close.index)
        
        sma = self._sma(close, period)
        std = close.rolling(window=period).std()
        upper = sma + (std * nbdevup)
        lower = sma - (std * nbdevdn)
        return upper, sma, lower
    
    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.ATR(high, low, close, timeperiod=period), index=close.index)
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def _stoch(self, high: pd.Series, low: pd.Series, close: pd.Series, fastk: int = 14, slowk: int = 3, slowd: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator."""
        if self.config.use_talib and TALIB_AVAILABLE:
            slowk, slowd = talib.STOCH(high, low, close, fastk_period=fastk, slowk_period=slowk, slowd_period=slowd)
            return pd.Series(slowk, index=close.index), pd.Series(slowd, index=close.index)
        
        lowest_low = low.rolling(window=fastk).min()
        highest_high = high.rolling(window=fastk).max()
        raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        slow_k = raw_k.rolling(window=slowk).mean()
        slow_d = slow_k.rolling(window=slowd).mean()
        return slow_k, slow_d
    
    def _adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average Directional Index."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.ADX(high, low, close, timeperiod=period), index=close.index)
        
        # Calcul simplifié
        atr = self._atr(high, low, close, period)
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(window=period).mean()
    
    def _cci(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Commodity Channel Index."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.CCI(high, low, close, timeperiod=period), index=close.index)
        
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mean_dev = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        return (tp - sma) / (0.015 * mean_dev)
    
    def _willr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Williams %R."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.WILLR(high, low, close, timeperiod=period), index=close.index)
        
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        return -100 * (highest_high - close) / (highest_high - lowest_low)
    
    def _roc(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Rate of Change."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.ROC(close, timeperiod=period), index=close.index)
        return (close / close.shift(period) - 1) * 100
    
    def _mom(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Momentum."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.MOM(close, timeperiod=period), index=close.index)
        return close - close.shift(period)
    
    def _obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume."""
        if self.config.use_talib and TALIB_AVAILABLE:
            return pd.Series(talib.OBV(close, volume), index=close.index)
        
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
    
    def _vwap(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price."""
        return (close * volume).cumsum() / volume.cumsum()
    
    def _ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ichimoku Cloud."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Tenkan-sen (Conversion Line)
        tenkan_sen = (high.rolling(window=9).max() + low.rolling(window=9).min()) / 2
        
        # Kijun-sen (Base Line)
        kijun_sen = (high.rolling(window=26).max() + low.rolling(window=26).min()) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        # Senkou Span B (Leading Span B)
        senkou_b = ((high.rolling(window=52).max() + low.rolling(window=52).min()) / 2).shift(26)
        
        # Chikou Span (Lagging Span)
        chikou_span = close.shift(-26)
        
        df['tenkan_sen'] = tenkan_sen
        df['kijun_sen'] = kijun_sen
        df['senkou_a'] = senkou_a
        df['senkou_b'] = senkou_b
        df['chikou_span'] = chikou_span
        
        return df
    
    # ============================================================
    # FEATURES STATISTIQUES
    # ============================================================
    
    def add_statistical_features(
        self,
        data: pd.DataFrame,
        windows: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Ajoute des features statistiques.
        
        Args:
            data: DataFrame.
            windows: Fenêtres de calcul.
            
        Returns:
            DataFrame avec features statistiques.
        """
        if not self.config.enable_statistical:
            return data
        
        if windows is None:
            windows = [5, 10, 20, 50]
        
        logger.info(f"Ajout de features statistiques avec fenêtres {windows}")
        
        df = data.copy()
        close = df['close']
        returns = close.pct_change()
        
        for window in windows:
            # Statistiques de base
            df[f'mean_{window}'] = close.rolling(window).mean()
            df[f'std_{window}'] = close.rolling(window).std()
            df[f'min_{window}'] = close.rolling(window).min()
            df[f'max_{window}'] = close.rolling(window).max()
            
            # Quantiles
            df[f'q25_{window}'] = close.rolling(window).quantile(0.25)
            df[f'q50_{window}'] = close.rolling(window).quantile(0.50)
            df[f'q75_{window}'] = close.rolling(window).quantile(0.75)
            
            # Skewness et Kurtosis
            df[f'skew_{window}'] = close.rolling(window).skew()
            df[f'kurt_{window}'] = close.rolling(window).kurt()
            
            # Z-score
            df[f'zscore_{window}'] = (close - df[f'mean_{window}']) / df[f'std_{window}']
            
            # Returns statistiques
            df[f'return_mean_{window}'] = returns.rolling(window).mean()
            df[f'return_std_{window}'] = returns.rolling(window).std()
            
            # Corrélation
            df[f'corr_close_volume_{window}'] = close.rolling(window).corr(df['volume'])
        
        # Features expandantes
        df['expanding_mean'] = close.expanding().mean()
        df['expanding_std'] = close.expanding().std()
        
        return df
    
    # ============================================================
    # FEATURES DE MARCHÉ
    # ============================================================
    
    def add_market_features(
        self,
        data: pd.DataFrame,
        orderbook: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Ajoute des features de marché.
        
        Args:
            data: DataFrame OHLCV.
            orderbook: Données du carnet d'ordres.
            
        Returns:
            DataFrame avec features de marché.
        """
        if not self.config.enable_market:
            return data
        
        logger.info("Ajout de features de marché")
        
        df = data.copy()
        
        # Volatilité
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['volatility_5'] = df['close'].pct_change().rolling(5).std()
        df['volatility_50'] = df['close'].pct_change().rolling(50).std()
        
        # Spread (bid-ask)
        if 'bid' in df.columns and 'ask' in df.columns:
            df['spread'] = (df['ask'] - df['bid']) / ((df['ask'] + df['bid']) / 2)
            df['spread_pct'] = (df['ask'] - df['bid']) / df['bid'] * 100
        
        # Liquidité
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Order Book Imbalance
        if orderbook is not None:
            df = self._add_orderbook_features(df, orderbook)
        
        return df
    
    def _add_orderbook_features(
        self,
        df: pd.DataFrame,
        orderbook: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Ajoute des features du carnet d'ordres.
        
        Args:
            df: DataFrame OHLCV.
            orderbook: Données du carnet d'ordres.
            
        Returns:
            DataFrame avec features.
        """
        # Imbalance
        if 'bid_volume' in orderbook.columns and 'ask_volume' in orderbook.columns:
            df['orderbook_imbalance'] = (orderbook['bid_volume'] - orderbook['ask_volume']) / (orderbook['bid_volume'] + orderbook['ask_volume'])
        
        # Profondeur
        if 'bid_depth' in orderbook.columns and 'ask_depth' in orderbook.columns:
            df['orderbook_depth'] = orderbook['bid_depth'] + orderbook['ask_depth']
        
        # Liquidité
        if 'total_liquidity' in orderbook.columns:
            df['orderbook_liquidity'] = orderbook['total_liquidity']
        
        return df
    
    # ============================================================
    # FEATURES AVANCÉES
    # ============================================================
    
    def add_advanced_features(
        self,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Ajoute des features avancées.
        
        Args:
            data: DataFrame.
            
        Returns:
            DataFrame avec features avancées.
        """
        df = data.copy()
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Support et Résistance
        df['support_level'] = self._find_support_resistance(close, 'support')
        df['resistance_level'] = self._find_support_resistance(close, 'resistance')
        
        # Waves (Elliot)
        df['wave_count'] = self._detect_waves(close)
        
        # Fourier
        df['fourier_trend'] = self._fourier_trend(close)
        
        # High/Low ratios
        df['hl_ratio'] = (high - low) / close
        df['co_ratio'] = (close - low) / (high - low)
        
        # Price to moving average
        df['p_to_ma_20'] = close / df['sma_20'] if 'sma_20' in df.columns else close / self._sma(close, 20)
        
        return df
    
    def _find_support_resistance(
        self,
        prices: pd.Series,
        level_type: str = 'support',
        window: int = 20
    ) -> pd.Series:
        """
        Trouve les niveaux de support et résistance.
        
        Args:
            prices: Série de prix.
            level_type: 'support' ou 'resistance'.
            window: Fenêtre de recherche.
            
        Returns:
            Série des niveaux.
        """
        rolling_max = prices.rolling(window).max()
        rolling_min = prices.rolling(window).min()
        
        if level_type == 'support':
            return rolling_min
        else:
            return rolling_max
    
    def _detect_waves(self, prices: pd.Series, min_distance: int = 5) -> pd.Series:
        """
        Détecte les vagues (Elliot Wave).
        
        Args:
            prices: Série de prix.
            min_distance: Distance minimale entre pics.
            
        Returns:
            Série des compteurs de vagues.
        """
        peaks, _ = find_peaks(prices, distance=min_distance)
        troughs, _ = find_peaks(-prices, distance=min_distance)
        
        wave_count = pd.Series(0, index=prices.index)
        
        all_points = sorted(list(peaks) + list(troughs))
        for i, point in enumerate(all_points):
            wave_count.iloc[point] = i % 5 + 1
        
        return wave_count.ffill().fillna(0)
    
    def _fourier_trend(self, prices: pd.Series, n_components: int = 5) -> pd.Series:
        """
        Extrait la tendance via transformée de Fourier.
        
        Args:
            prices: Série de prix.
            n_components: Nombre de composantes.
            
        Returns:
            Série de la tendance.
        """
        n = len(prices)
        fft_vals = fft(prices.values)
        
        # Garder les composantes principales
        fft_vals[n_components:-n_components] = 0
        
        # Reconstruction
        trend = ifft(fft_vals).real
        return pd.Series(trend, index=prices.index)
    
    # ============================================================
    # PROCESSUS PRINCIPAL
    # ============================================================
    
    def process_features(
        self,
        data: pd.DataFrame,
        include_technical: bool = True,
        include_statistical: bool = True,
        include_market: bool = True,
        include_advanced: bool = True
    ) -> pd.DataFrame:
        """
        Traite toutes les features.
        
        Args:
            data: Données à traiter.
            include_technical: Inclure les indicateurs techniques.
            include_statistical: Inclure les features statistiques.
            include_market: Inclure les features de marché.
            include_advanced: Inclure les features avancées.
            
        Returns:
            DataFrame avec toutes les features.
        """
        start_time = time.time()
        
        logger.info("Début du traitement des features")
        
        df = data.copy()
        
        # Indicateurs techniques
        if include_technical and self.config.enable_technical:
            df = self.add_technical_indicators(df)
        
        # Features statistiques
        if include_statistical and self.config.enable_statistical:
            df = self.add_statistical_features(df)
        
        # Features de marché
        if include_market and self.config.enable_market:
            df = self.add_market_features(df)
        
        # Features avancées
        if include_advanced:
            df = self.add_advanced_features(df)
        
        # Normalisation
        if self.config.normalize_output:
            df = self._normalize_features(df)
        
        # Nettoyage
        df = self._clean_features(df)
        
        # Métriques
        processing_time = time.time() - start_time
        self._stats['total_processed'] += len(df)
        self._stats['total_features'] += len(df.columns) - len(data.columns)
        self._stats['processing_time'] += processing_time
        
        logger.info(f"Traitement terminé: {len(df.columns)} features, {processing_time:.3f}s")
        
        return df
    
    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalise les features.
        
        Args:
            df: DataFrame.
            
        Returns:
            DataFrame normalisé.
        """
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = (df[numeric_cols] - df[numeric_cols].mean()) / df[numeric_cols].std()
        return df
    
    def _clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Nettoie les features.
        
        Args:
            df: DataFrame.
            
        Returns:
            DataFrame nettoyé.
        """
        # Suppression des colonnes avec trop de NaN
        df = df.dropna(thresh=len(df) * 0.8, axis=1)
        
        # Suppression des colonnes avec variance nulle
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if df[col].std() == 0:
                df = df.drop(columns=[col])
        
        # Remplissage des NaN
        df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        # Limitation des valeurs extrêmes
        for col in numeric_cols:
            if col in df.columns:
                q1 = df[col].quantile(0.01)
                q3 = df[col].quantile(0.99)
                df[col] = df[col].clip(q1, q3)
        
        return df
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def get_feature_importance(
        self,
        df: pd.DataFrame,
        target: str = 'close'
    ) -> pd.DataFrame:
        """
        Calcule l'importance des features.
        
        Args:
            df: DataFrame avec features.
            target: Colonne cible.
            
        Returns:
            DataFrame des importances.
        """
        importances = {}
        
        for col in df.columns:
            if col != target:
                corr = df[col].corr(df[target])
                importances[col] = abs(corr)
        
        return pd.DataFrame({
            'feature': list(importances.keys()),
            'importance': list(importances.values())
        }).sort_values('importance', ascending=False)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du processeur.
        
        Returns:
            Statistiques.
        """
        return self._stats.copy()
    
    def reset(self) -> None:
        """
        Réinitialise le processeur.
        """
        self._cache.clear()
        self._cache_timestamps.clear()
        self._stats = {
            'total_processed': 0,
            'total_features': 0,
            'processing_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        logger.info("DataProcessor réinitialisé")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_processor(
    mode: str = "auto",
    use_talib: bool = True,
    **kwargs
) -> DataProcessor:
    """
    Crée un processeur avec configuration simplifiée.
    
    Args:
        mode: Mode de traitement ('cpu', 'gpu', 'auto').
        use_talib: Utiliser TA-Lib.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du DataProcessor.
    """
    mode_map = {
        'cpu': ProcessingMode.CPU,
        'gpu': ProcessingMode.GPU,
        'auto': ProcessingMode.AUTO
    }
    
    config = ProcessingConfig(
        mode=mode_map.get(mode, ProcessingMode.AUTO),
        use_talib=use_talib,
        **kwargs
    )
    return DataProcessor(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataProcessor',
    'ProcessingConfig',
    'ProcessingMode',
    'FeatureCategory',
    'FeatureSet',

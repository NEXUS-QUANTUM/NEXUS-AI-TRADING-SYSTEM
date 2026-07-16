"""
NEXUS AI TRADING SYSTEM - Data Provider
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/data_provider.py
Description: Fournisseur de données historiques pour le backtesting.
             Supporte multiples sources: fichiers locaux, base de données,
             APIs externes (Yahoo Finance, Alpha Vantage, etc.)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import aiohttp
import aiofiles
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_log, after_log
)

from shared.constants.time_constants import (
    TIMEFRAME_1M, TIMEFRAME_5M, TIMEFRAME_15M,
    TIMEFRAME_1H, TIMEFRAME_4H, TIMEFRAME_1D,
    TIMEFRAME_1W, TIMEFRAME_1M, TIMEFRAME_1Y
)
from shared.helpers.date_helpers import (
    timestamp_to_datetime, datetime_to_timestamp,
    parse_timeframe, get_timeframe_delta
)
from shared.helpers.number_helpers import round_decimal
from shared.exceptions import (
    DataProviderError, DataNotFoundError,
    RateLimitError, APIError
)
from shared.validators.market_validator import validate_symbol

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class DataSource:
    """
    Configuration d'une source de données.
    """
    name: str
    type: str  # 'file', 'database', 'api'
    enabled: bool = True
    priority: int = 10  # Plus bas = plus prioritaire
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataCache:
    """
    Cache de données.
    """
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: int = 3600  # Secondes
    
    def is_expired(self) -> bool:
        """Vérifie si le cache est expiré."""
        return (datetime.now() - self.timestamp).total_seconds() > self.ttl


class DataProvider:
    """
    Fournisseur de données historiques.
    Supporte le caching, la pagination et la compression.
    """
    
    def __init__(
        self,
        cache_dir: str = "data/cache/",
        cache_ttl: int = 86400,  # 24 heures
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Initialise le fournisseur de données.
        
        Args:
            cache_dir: Répertoire de cache.
            cache_ttl: Durée de vie du cache en secondes.
            max_retries: Nombre maximum de tentatives.
            timeout: Timeout des requêtes.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Cache mémoire
        self._memory_cache: Dict[str, DataCache] = {}
        
        # Sources de données
        self.sources: List[DataSource] = []
        self._initialize_sources()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info("DataProvider initialisé")
        logger.info(f"Répertoire de cache: {self.cache_dir}")
    
    def _initialize_sources(self) -> None:
        """
        Initialise les sources de données par défaut.
        """
        # Sources locales
        self.sources.append(DataSource(
            name="local_files",
            type="file",
            priority=1,
            config={"path": "data/historical/"}
        ))
        
        # Sources base de données (si disponible)
        # self.sources.append(DataSource(...))
        
        # Sources API
        self.sources.append(DataSource(
            name="yahoo_finance",
            type="api",
            priority=20,
            config={"base_url": "https://query1.finance.yahoo.com/v8/finance/chart/"}
        ))
        
        self.sources.append(DataSource(
            name="alphavantage",
            type="api",
            priority=30,
            config={"base_url": "https://www.alphavantage.co/query/"}
        ))
        
        self.sources.append(DataSource(
            name="twelvedata",
            type="api",
            priority=40,
            config={"base_url": "https://api.twelvedata.com/"}
        ))
        
        # Trier par priorité
        self.sources.sort(key=lambda x: x.priority)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Retourne une session HTTP réutilisable.
        
        Returns:
            Session HTTP.
        """
        if self._session is None:
            connector = aiohttp.TCPConnector(
                limit=100,
                ttl_dns_cache=300,
                keepalive_timeout=30
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self) -> None:
        """Ferme la session HTTP."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = TIMEFRAME_1H,
        source: Optional[str] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Récupère les données historiques (interface synchrone).
        
        Args:
            symbol: Symbole à récupérer.
            start_date: Date de début.
            end_date: Date de fin.
            timeframe: Timeframe des données.
            source: Source spécifique (None = auto).
            use_cache: Utiliser le cache.
            force_refresh: Forcer le rafraîchissement.
            
        Returns:
            DataFrame contenant les données OHLCV.
            
        Raises:
            DataNotFoundError: Si les données ne sont pas trouvées.
            DataProviderError: En cas d'erreur.
        """
        # Validation
        validate_symbol(symbol)
        
        # Conversion des dates
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
        
        if start_date >= end_date:
            raise DataProviderError("Start date must be before end date")
        
        # Exécution asynchrone
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si déjà dans une boucle asynchrone
            future = asyncio.ensure_future(
                self.get_historical_data_async(
                    symbol, start_date, end_date,
                    timeframe, source, use_cache, force_refresh
                )
            )
            return future.result()
        else:
            # Exécution synchrone
            return loop.run_until_complete(
                self.get_historical_data_async(
                    symbol, start_date, end_date,
                    timeframe, source, use_cache, force_refresh
                )
            )
    
    async def get_historical_data_async(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = TIMEFRAME_1H,
        source: Optional[str] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Récupère les données historiques (asynchrone).
        
        Args:
            symbol: Symbole à récupérer.
            start_date: Date de début.
            end_date: Date de fin.
            timeframe: Timeframe des données.
            source: Source spécifique (None = auto).
            use_cache: Utiliser le cache.
            force_refresh: Forcer le rafraîchissement.
            
        Returns:
            DataFrame contenant les données OHLCV.
            
        Raises:
            DataNotFoundError: Si les données ne sont pas trouvées.
            DataProviderError: En cas d'erreur.
        """
        # Génération de la clé de cache
        cache_key = self._generate_cache_key(
            symbol, start_date, end_date, timeframe, source
        )
        
        # Vérification du cache
        if use_cache and not force_refresh:
            cached_data = await self._get_from_cache(cache_key)
            if cached_data is not None:
                logger.debug(f"Données récupérées du cache: {cache_key}")
                return cached_data
        
        # Récupération des données
        data = None
        errors = []
        
        # Sélection de la source
        if source:
            sources = [s for s in self.sources if s.name == source]
            if not sources:
                raise DataProviderError(f"Source '{source}' non trouvée")
            sources_to_try = sources
        else:
            sources_to_try = [s for s in self.sources if s.enabled]
        
        # Tentative avec chaque source
        for src in sources_to_try:
            try:
                logger.debug(f"Tentative avec {src.name}...")
                
                if src.type == "file":
                    data = await self._load_from_file(
                        symbol, start_date, end_date,
                        timeframe, src.config
                    )
                elif src.type == "database":
                    data = await self._load_from_database(
                        symbol, start_date, end_date,
                        timeframe, src.config
                    )
                elif src.type == "api":
                    data = await self._load_from_api(
                        symbol, start_date, end_date,
                        timeframe, src.config
                    )
                else:
                    continue
                
                if data is not None and not data.empty:
                    logger.info(
                        f"Données récupérées de {src.name}: "
                        f"{len(data)} bars"
                    )
                    break
                    
            except Exception as e:
                error_msg = f"{src.name}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        # Vérification des données
        if data is None or data.empty:
            raise DataNotFoundError(
                f"Aucune donnée trouvée pour {symbol} "
                f"de {start_date} à {end_date}. "
                f"Erreurs: {'; '.join(errors)}"
            )
        
        # Nettoyage et standardisation
        data = self._clean_data(data, symbol, timeframe)
        
        # Mise en cache
        if use_cache and not force_refresh:
            await self._save_to_cache(cache_key, data)
        
        return data
    
    async def _load_from_file(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        config: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """
        Charge les données depuis un fichier.
        
        Args:
            symbol: Symbole.
            start_date: Date de début.
            end_date: Date de fin.
            timeframe: Timeframe.
            config: Configuration.
            
        Returns:
            DataFrame ou None.
        """
        path = Path(config.get("path", "data/historical/"))
        filename = f"{symbol}_{timeframe}.parquet"
        filepath = path / filename
        
        if not filepath.exists():
            # Essayer avec un nom alternatif
            filename_alt = f"{symbol}_{timeframe}.csv"
            filepath_alt = path / filename_alt
            if filepath_alt.exists():
                filepath = filepath_alt
            else:
                return None
        
        try:
            if filepath.suffix == '.parquet':
                data = pd.read_parquet(filepath)
            elif filepath.suffix == '.csv':
                data = pd.read_csv(filepath, parse_dates=['timestamp'])
            else:
                return None
            
            # Filtrage par date
            data = data[
                (data['timestamp'] >= start_date) &
                (data['timestamp'] <= end_date)
            ].copy()
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur de chargement du fichier {filepath}: {e}")
            return None
    
    async def _load_from_database(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        config: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """
        Charge les données depuis la base de données.
        
        Args:
            symbol: Symbole.
            start_date: Date de début.
            end_date: Date de fin.
            timeframe: Timeframe.
            config: Configuration.
            
        Returns:
            DataFrame ou None.
        """
        # Implémentation de la base de données
        # À compléter selon la configuration
        return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((APIError, RateLimitError)),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.INFO)
    )
    async def _load_from_api(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        config: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """
        Charge les données depuis une API.
        
        Args:
            symbol: Symbole.
            start_date: Date de début.
            end_date: Date de fin.
            timeframe: Timeframe.
            config: Configuration.
            
        Returns:
            DataFrame ou None.
            
        Raises:
            APIError: En cas d'erreur API.
            RateLimitError: En cas de rate limit.
        """
        base_url = config.get('base_url')
        if not base_url:
            return None
        
        # Conversion des dates en timestamp
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())
        
        # Construction de la requête
        params = {
            'symbol': symbol,
            'interval': self._timeframe_to_interval(timeframe),
            'start': start_ts,
            'end': end_ts
        }
        
        # Ajout de l'API key si disponible
        api_key = config.get('api_key') or os.getenv('DATA_API_KEY')
        if api_key:
            params['apikey'] = api_key
        
        url = f"{base_url}/{symbol}"
        
        try:
            session = await self._get_session()
            
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    raise RateLimitError("Rate limit exceeded")
                elif response.status != 200:
                    error_text = await response.text()
                    raise APIError(
                        f"API error {response.status}: {error_text}"
                    )
                
                data = await response.json()
                
                # Parsing selon l'API
                if 'yahoo' in base_url:
                    return self._parse_yahoo_data(data, symbol)
                elif 'alphavantage' in base_url:
                    return self._parse_alphavantage_data(data, symbol)
                elif 'twelvedata' in base_url:
                    return self._parse_twelvedata_data(data, symbol)
                else:
                    # Essayer de parser automatiquement
                    return self._parse_generic_data(data, symbol)
                    
        except aiohttp.ClientError as e:
            raise APIError(f"HTTP client error: {e}")
        except json.JSONDecodeError as e:
            raise APIError(f"JSON parsing error: {e}")
    
    def _parse_yahoo_data(
        self,
        data: Dict[str, Any],
        symbol: str
    ) -> pd.DataFrame:
        """Parse les données de Yahoo Finance."""
        try:
            chart = data.get('chart', {})
            result = chart.get('result', [])
            
            if not result:
                raise DataNotFoundError(f"Yahoo: Aucun résultat pour {symbol}")
            
            item = result[0]
            timestamps = item.get('timestamp', [])
            indicators = item.get('indicators', {})
            quote = indicators.get('quote', [{}])[0]
            
            # Extraction des données
            df = pd.DataFrame({
                'timestamp': [datetime.fromtimestamp(ts) for ts in timestamps],
                'open': quote.get('open', []),
                'high': quote.get('high', []),
                'low': quote.get('low', []),
                'close': quote.get('close', []),
                'volume': quote.get('volume', [])
            })
            
            # Suppression des lignes avec des NaN
            df = df.dropna()
            
            return df
            
        except Exception as e:
            raise DataNotFoundError(f"Yahoo: Erreur de parsing: {e}")
    
    def _parse_alphavantage_data(
        self,
        data: Dict[str, Any],
        symbol: str
    ) -> pd.DataFrame:
        """Parse les données de Alpha Vantage."""
        try:
            # Recherche de la clé de time series
            time_series_key = None
            for key in data.keys():
                if 'Time Series' in key:
                    time_series_key = key
                    break
            
            if not time_series_key:
                raise DataNotFoundError(
                    f"Alpha Vantage: Aucune time series pour {symbol}"
                )
            
            time_series = data[time_series_key]
            df_data = []
            
            for dt_str, values in time_series.items():
                dt = datetime.fromisoformat(dt_str)
                df_data.append({
                    'timestamp': dt,
                    'open': float(values.get('1. open', 0)),
                    'high': float(values.get('2. high', 0)),
                    'low': float(values.get('3. low', 0)),
                    'close': float(values.get('4. close', 0)),
                    'volume': float(values.get('5. volume', 0))
                })
            
            df = pd.DataFrame(df_data)
            df = df.sort_values('timestamp')
            
            return df
            
        except Exception as e:
            raise DataNotFoundError(f"Alpha Vantage: Erreur de parsing: {e}")
    
    def _parse_twelvedata_data(
        self,
        data: Dict[str, Any],
        symbol: str
    ) -> pd.DataFrame:
        """Parse les données de Twelve Data."""
        try:
            values = data.get('values', [])
            if not values:
                raise DataNotFoundError(
                    f"Twelve Data: Aucune valeur pour {symbol}"
                )
            
            df_data = []
            for item in values:
                dt = datetime.fromisoformat(item.get('datetime'))
                df_data.append({
                    'timestamp': dt,
                    'open': float(item.get('open', 0)),
                    'high': float(item.get('high', 0)),
                    'low': float(item.get('low', 0)),
                    'close': float(item.get('close', 0)),
                    'volume': float(item.get('volume', 0))
                })
            
            df = pd.DataFrame(df_data)
            df = df.sort_values('timestamp')
            
            return df
            
        except Exception as e:
            raise DataNotFoundError(f"Twelve Data: Erreur de parsing: {e}")
    
    def _parse_generic_data(
        self,
        data: Dict[str, Any],
        symbol: str
    ) -> pd.DataFrame:
        """
        Parse générique pour différentes APIs.
        """
        # Tentative de détection automatique
        df_data = []
        
        for item in data:
            # Recherche des colonnes standard
            dt = None
            for key in ['timestamp', 'time', 'date', 'datetime']:
                if key in item:
                    dt = item[key]
                    break
            
            if dt is None:
                continue
            
            if isinstance(dt, (int, float)):
                dt = datetime.fromtimestamp(dt)
            elif isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                except ValueError:
                    continue
            
            df_data.append({
                'timestamp': dt,
                'open': float(item.get('open', item.get('o', 0))),
                'high': float(item.get('high', item.get('h', 0))),
                'low': float(item.get('low', item.get('l', 0))),
                'close': float(item.get('close', item.get('c', 0))),
                'volume': float(item.get('volume', item.get('v', 0)))
            })
        
        if not df_data:
            raise DataNotFoundError("Generic: Aucune donnée parsable")
        
        df = pd.DataFrame(df_data)
        df = df.sort_values('timestamp')
        
        return df
    
    def _clean_data(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Nettoie et standardise les données.
        
        Args:
            data: DataFrame brut.
            symbol: Symbole.
            timeframe: Timeframe.
            
        Returns:
            DataFrame nettoyé.
        """
        # Copie pour éviter les modifications
        df = data.copy()
        
        # Vérification des colonnes requises
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                raise DataProviderError(f"Colonne '{col}' manquante")
        
        # Conversion des types
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Tri par timestamp
        df = df.sort_values('timestamp')
        
        # Suppression des doublons
        df = df.drop_duplicates(subset=['timestamp'])
        
        # Suppression des lignes avec des NaN
        df = df.dropna()
        
        # Suppression des zéros et valeurs négatives
        df = df[df['volume'] > 0]
        df = df[df['close'] > 0]
        df = df[df['high'] > 0]
        df = df[df['low'] > 0]
        
        # Vérification que high >= low
        df = df[df['high'] >= df['low']]
        
        # Resampling si nécessaire
        if timeframe not in [TIMEFRAME_1M, TIMEFRAME_5M, TIMEFRAME_15M,
                             TIMEFRAME_1H, TIMEFRAME_4H, TIMEFRAME_1D,
                             TIMEFRAME_1W, TIMEFRAME_1M, TIMEFRAME_1Y]:
            # Resampling personnalisé
            delta = get_timeframe_delta(timeframe)
            if delta:
                df = self._resample_data(df, delta)
        
        # Ajout de métadonnées
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        
        logger.debug(
            f"Données nettoyées: {len(df)} bars "
            f"({df['timestamp'].min()} -> {df['timestamp'].max()})"
        )
        
        return df
    
    def _resample_data(
        self,
        data: pd.DataFrame,
        freq: str
    ) -> pd.DataFrame:
        """
        Resample les données à une fréquence différente.
        
        Args:
            data: DataFrame original.
            freq: Fréquence de resampling.
            
        Returns:
            DataFrame resamplé.
        """
        # Mise en index
        df = data.set_index('timestamp')
        
        # Resampling OHLCV
        resampled = df.resample(freq).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # Suppression des NaN
        resampled = resampled.dropna()
        
        # Réinitialisation de l'index
        resampled = resampled.reset_index()
        
        return resampled
    
    def _generate_cache_key(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        source: Optional[str] = None
    ) -> str:
        """
        Génère une clé de cache unique.
        
        Returns:
            Clé de cache.
        """
        source_str = source or "auto"
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        return f"{symbol}_{timeframe}_{start_str}_{end_str}_{source_str}.parquet"
    
    async def _get_from_cache(self, key: str) -> Optional[pd.DataFrame]:
        """
        Récupère les données du cache.
        
        Args:
            key: Clé de cache.
            
        Returns:
            DataFrame ou None.
        """
        # Vérification du cache mémoire
        if key in self._memory_cache:
            cache_entry = self._memory_cache[key]
            if not cache_entry.is_expired():
                return cache_entry.data
        
        # Vérification du cache disque
        cache_path = self.cache_dir / key
        
        if cache_path.exists():
            try:
                # Vérification de l'âge du fichier
                file_age = time.time() - cache_path.stat().st_mtime
                if file_age < self.cache_ttl:
                    async with aiofiles.open(cache_path, 'rb') as f:
                        content = await f.read()
                    
                    data = pd.read_parquet(cache_path)
                    
                    # Mise en cache mémoire
                    self._memory_cache[key] = DataCache(
                        data=data,
                        timestamp=datetime.now(),
                        ttl=self.cache_ttl
                    )
                    
                    return data
                    
            except Exception as e:
                logger.warning(f"Erreur de lecture du cache {key}: {e}")
        
        return None
    
    async def _save_to_cache(self, key: str, data: pd.DataFrame) -> None:
        """
        Sauvegarde les données dans le cache.
        
        Args:
            key: Clé de cache.
            data: Données à sauvegarder.
        """
        try:
            # Sauvegarde disque
            cache_path = self.cache_dir / key
            data.to_parquet(cache_path)
            
            # Sauvegarde mémoire
            self._memory_cache[key] = DataCache(
                data=data,
                timestamp=datetime.now(),
                ttl=self.cache_ttl
            )
            
        except Exception as e:
            logger.warning(f"Erreur de sauvegarde du cache {key}: {e}")
    
    def _timeframe_to_interval(self, timeframe: str) -> str:
        """
        Convertit un timeframe interne en intervalle API.
        
        Args:
            timeframe: Timeframe interne.
            
        Returns:
            Intervalle API.
        """
        mapping = {
            TIMEFRAME_1M: '1m',
            TIMEFRAME_5M: '5m',
            TIMEFRAME_15M: '15m',
            TIMEFRAME_1H: '1h',
            TIMEFRAME_4H: '4h',
            TIMEFRAME_1D: '1d',
            TIMEFRAME_1W: '1w',
            TIMEFRAME_1M: '1mo',
            TIMEFRAME_1Y: '1y'
        }
        return mapping.get(timeframe, '1d')
    
    async def get_latest_price(self, symbol: str) -> float:
        """
        Récupère le dernier prix d'un symbole.
        
        Args:
            symbol: Symbole.
            
        Returns:
            Dernier prix.
        """
        data = await self.get_historical_data_async(
            symbol=symbol,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
            timeframe=TIMEFRAME_1H
        )
        
        if data.empty:
            raise DataNotFoundError(f"Aucun prix pour {symbol}")
        
        return float(data.iloc[-1]['close'])
    
    async def get_batch_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = TIMEFRAME_1H
    ) -> Dict[str, pd.DataFrame]:
        """
        Récupère les données pour plusieurs symboles.
        
        Args:
            symbols: Liste des symboles.
            start_date: Date de début.
            end_date: Date de fin.
            timeframe: Timeframe.
            
        Returns:
            Dictionnaire {symbole: DataFrame}.
        """
        results = {}
        
        # Récupération parallèle
        tasks = []
        for symbol in symbols:
            task = self.get_historical_data_async(
                symbol, start_date, end_date, timeframe
            )
            tasks.append(task)
        
        # Exécution parallèle
        data_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, data in enumerate(data_list):
            symbol = symbols[i]
            
            if isinstance(data, Exception):
                logger.warning(f"Erreur pour {symbol}: {data}")
                results[symbol] = pd.DataFrame()
            else:
                results[symbol] = data
        
        return results
    
    def get_available_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles disponibles.
        
        Returns:
            Liste des symboles.
        """
        symbols = []
        
        # Recherche dans les fichiers
        data_path = Path("data/historical/")
        if data_path.exists():
            for file in data_path.glob("*.parquet"):
                symbol = file.stem.split('_')[0]
                if symbol not in symbols:
                    symbols.append(symbol)
            
            for file in data_path.glob("*.csv"):
                symbol = file.stem.split('_')[0]
                if symbol not in symbols:
                    symbols.append(symbol)
        
        return sorted(symbols)
    
    def clear_cache(self, key: Optional[str] = None) -> None:
        """
        Vide le cache.
        
        Args:
            key: Clé spécifique ou None pour tout vider.
        """
        if key:
            # Vider une clé spécifique
            self._memory_cache.pop(key, None)
            cache_path = self.cache_dir / key
            if cache_path.exists():
                cache_path.unlink()
            logger.info(f"Cache vidé: {key}")
        else:
            # Vider tout le cache
            self._memory_cache.clear()
            for file in self.cache_dir.glob("*.parquet"):
                file.unlink()
            logger.info("Cache entièrement vidé")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du cache.
        
        Returns:
            Statistiques du cache.
        """
        memory_count = len(self._memory_cache)
        disk_files = list(self.cache_dir.glob("*.parquet"))
        disk_size = sum(f.stat().st_size for f in disk_files) / (1024 * 1024)  # MB
        
        return {
            "memory_cached": memory_count,
            "disk_files": len(disk_files),
            "disk_size_mb": round(disk_size, 2),
            "cache_dir": str(self.cache_dir)
        }


# Fonctions utilitaires
def get_data_provider() -> DataProvider:
    """
    Retourne une instance singleton du DataProvider.
    
    Returns:
        Instance du DataProvider.
    """
    # Simple singleton pour l'utilisation
    if not hasattr(get_data_provider, "_instance"):
        get_data_provider._instance = DataProvider()
    return get_data_provider._instance


# Exportation
__all__ = [
    'DataProvider',
    'DataSource',
    'DataCache',
    'get_data_provider'
]

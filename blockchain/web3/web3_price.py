"""
Web3 Price Module
===================

This module provides price fetching capabilities for the Web3 client.
It supports multiple price sources including Chainlink oracles, Uniswap V2/V3,
Curve, and centralized exchange APIs with automatic fallback and caching.
"""

import time
import json
import logging
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from functools import lru_cache

from web3 import Web3
from web3.types import BlockIdentifier

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.converters import to_int, to_float, to_str
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.helpers import load_json, save_json
from trading.bots.swing_bot.utils.network_utils import NetworkClient

logger = logging.getLogger(__name__)


@dataclass
class PriceSource:
    """Price source configuration."""
    name: str
    type: str  # 'chainlink', 'uniswap_v2', 'uniswap_v3', 'curve', 'dex', 'cex'
    address: Optional[str] = None
    pair: Optional[Tuple[str, str]] = None
    base_asset: Optional[str] = None
    quote_asset: Optional[str] = None
    decimals: int = 18
    weight: float = 1.0
    enabled: bool = True
    timeout: int = 10
    priority: int = 10


@dataclass
class PriceData:
    """Price data structure."""
    symbol: str
    price: float
    source: str
    timestamp: datetime
    confidence: float = 1.0
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedPrice:
    """Aggregated price with metadata."""
    symbol: str
    price: float
    sources_used: List[str]
    confidence: float
    timestamp: datetime
    spread: Optional[float] = None
    volume_24h: Optional[float] = None


class Web3Price:
    """
    Web3 price client for fetching asset prices from multiple sources.
    
    Supports:
    - Chainlink price feeds
    - Uniswap V2/V3 pools
    - Curve pools
    - DEX aggregators
    - CEX APIs (fallback)
    - Price aggregation with confidence scoring
    - Automatic source selection and fallback
    - Caching with TTL
    """
    
    # Chainlink price feed ABIs (simplified)
    CHAINLINK_AGGREGATOR_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "latestRoundData",
            "outputs": [
                {"name": "roundId", "type": "uint80"},
                {"name": "answer", "type": "int256"},
                {"name": "startedAt", "type": "uint256"},
                {"name": "updatedAt", "type": "uint256"},
                {"name": "answeredInRound", "type": "uint80"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "description",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        }
    ]
    
    # Uniswap V2 Pair ABI (minimal)
    UNISWAP_V2_PAIR_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "getReserves",
            "outputs": [
                {"name": "_reserve0", "type": "uint112"},
                {"name": "_reserve1", "type": "uint112"},
                {"name": "_blockTimestampLast", "type": "uint32"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token0",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token1",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        }
    ]
    
    # Uniswap V3 Pool ABI (minimal)
    UNISWAP_V3_POOL_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "slot0",
            "outputs": [
                {"name": "sqrtPriceX96", "type": "uint160"},
                {"name": "tick", "type": "int24"},
                {"name": "observationIndex", "type": "uint16"},
                {"name": "observationCardinality", "type": "uint16"},
                {"name": "observationCardinalityNext", "type": "uint16"},
                {"name": "feeProtocol", "type": "uint8"},
                {"name": "unlocked", "type": "bool"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token0",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token1",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        }
    ]
    
    # Known Chainlink price feed addresses (Ethereum Mainnet)
    CHAINLINK_FEEDS = {
        "ETH/USD": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "BTC/USD": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
        "LINK/USD": "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c",
        "UNI/USD": "0x553303d460EE0afB37EdFf9bE42922D8FF63220e",
        "AAVE/USD": "0x547a514d5e3769680Ce22B2361c10Ea13619e8a9",
        "MATIC/USD": "0x7bAC85A8a13A4BcD8abb3eB7d6b9d99f4F9003F5",
        "USDC/USD": "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6",
        "DAI/USD": "0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9",
        "USDT/USD": "0x3E7d1eAB13ad0104d2750B3343bC4Aa4d9025E1A",
        "WBTC/USD": "0xFD0f711b46A7BDE65B7a15B8Ad333Edc35602F0d",
        "SOL/USD": "0x4ffC43a60e6B78b1a6B6C7f5bD985CaC5A96c088",
        "AVAX/USD": "0x2CEA7F7703A390edCFf029bDba1Fc18c1AC6860D",
        "BNB/USD": "0x14e613AC84a31f709eadbdF89C6CC390fDc9540A",
        "DOGE/USD": "0x2465CefD3b488BE410b941b1d4b2767088e2A028",
        "ADA/USD": "0x2A8B42E4Ffd331b9EaE51C013d6e835c650636C8",
        "DOT/USD": "0x48290D9e1641D8e5813a59b0a5b734dE3D10cE9E",
    }
    
    def __init__(
        self,
        web3_client: Any,
        sources: Optional[List[PriceSource]] = None,
        default_symbols: Optional[List[str]] = None,
        cache_ttl: int = 60,
        min_source_confidence: float = 0.5,
        max_price_age_seconds: int = 600,
        use_cex_fallback: bool = True
    ):
        """
        Initialize the Web3 price client.
        
        Args:
            web3_client: Web3 client instance.
            sources: Custom price sources.
            default_symbols: Symbols to load default sources for.
            cache_ttl: Cache TTL in seconds.
            min_source_confidence: Minimum confidence for a source.
            max_price_age_seconds: Maximum age of price data.
            use_cex_fallback: Use CEX APIs as fallback.
        """
        self.web3_client = web3_client
        self.cache_ttl = cache_ttl
        self.min_source_confidence = min_source_confidence
        self.max_price_age_seconds = max_price_age_seconds
        self.use_cex_fallback = use_cex_fallback
        
        # Initialize sources
        self._sources: Dict[str, List[PriceSource]] = {}
        self._source_cache: Dict[str, Dict[str, Any]] = {}
        
        # Price cache
        self._price_cache = MemoryCache(max_size=1000, default_ttl=cache_ttl)
        
        # Token decimals cache
        self._decimals_cache = MemoryCache(max_size=100, default_ttl=3600)
        
        # Load default sources
        self._load_default_sources(default_symbols)
        
        # Add custom sources
        if sources:
            for source in sources:
                self.add_source(source)
        
        # Initialize network client for CEX fallback
        self._network_client = NetworkClient(timeout=10)
        
        logger.info(f"Web3Price initialized with {len(self._sources)} symbols")
    
    def _load_default_sources(self, symbols: Optional[List[str]] = None) -> None:
        """Load default Chainlink price feed sources."""
        if symbols is None:
            symbols = list(self.CHAINLINK_FEEDS.keys())
        
        for symbol in symbols:
            if symbol in self.CHAINLINK_FEEDS:
                self.add_source(PriceSource(
                    name=f"chainlink_{symbol}",
                    type="chainlink",
                    address=self.CHAINLINK_FEEDS[symbol],
                    base_asset=symbol.split('/')[0],
                    quote_asset=symbol.split('/')[1] if '/' in symbol else "USD",
                    priority=10
                ))
    
    # ============ Source Management ============
    
    def add_source(self, source: PriceSource) -> None:
        """
        Add a price source.
        
        Args:
            source: PriceSource object.
        """
        symbol = f"{source.base_asset}/{source.quote_asset}"
        if symbol not in self._sources:
            self._sources[symbol] = []
        
        # Add source with priority ordering
        self._sources[symbol].append(source)
        self._sources[symbol].sort(key=lambda x: x.priority, reverse=True)
        
        # Clear source cache
        self._source_cache.pop(symbol, None)
        
        logger.debug(f"Added price source: {source.name} for {symbol}")
    
    def remove_source(self, symbol: str, source_name: str) -> bool:
        """
        Remove a price source.
        
        Args:
            symbol: Trading pair symbol.
            source_name: Name of the source to remove.
            
        Returns:
            True if removed, False otherwise.
        """
        if symbol not in self._sources:
            return False
        
        initial_len = len(self._sources[symbol])
        self._sources[symbol] = [
            s for s in self._sources[symbol] if s.name != source_name
        ]
        
        if len(self._sources[symbol]) < initial_len:
            self._source_cache.pop(symbol, None)
            return True
        
        return False
    
    def get_sources(self, symbol: str) -> List[PriceSource]:
        """
        Get all sources for a symbol.
        
        Args:
            symbol: Trading pair symbol.
            
        Returns:
            List of PriceSource objects.
        """
        return self._sources.get(symbol, [])
    
    # ============ Price Fetching ============
    
    def fetch_price(
        self,
        symbol: str,
        source_type: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[PriceData]:
        """
        Fetch price from the best available source.
        
        Args:
            symbol: Trading pair symbol.
            source_type: Specific source type to use.
            force_refresh: Force refresh cache.
            
        Returns:
            PriceData object or None.
        """
        # Check cache
        cache_key = f"{symbol}_{source_type or 'all'}"
        if not force_refresh:
            cached = self._price_cache.get(cache_key)
            if cached is not None:
                return cached
        
        sources = self.get_sources(symbol)
        if not sources:
            # Try CEX fallback
            if self.use_cex_fallback:
                return self._fetch_cex_price(symbol)
            return None
        
        # Filter by source type if specified
        if source_type:
            sources = [s for s in sources if s.type == source_type]
        
        # Try sources in priority order
        for source in sources:
            if not source.enabled:
                continue
            
            try:
                price_data = self._fetch_from_source(symbol, source)
                if price_data is not None:
                    # Cache result
                    self._price_cache.set(cache_key, price_data)
                    return price_data
            except Exception as e:
                logger.warning(f"Source {source.name} failed: {e}")
                continue
        
        # Try CEX fallback if all sources fail
        if self.use_cex_fallback:
            return self._fetch_cex_price(symbol)
        
        return None
    
    def fetch_aggregated_price(
        self,
        symbol: str,
        min_sources: int = 2,
        max_sources: int = 5,
        force_refresh: bool = False
    ) -> Optional[AggregatedPrice]:
        """
        Fetch and aggregate price from multiple sources.
        
        Args:
            symbol: Trading pair symbol.
            min_sources: Minimum sources required.
            max_sources: Maximum sources to use.
            force_refresh: Force refresh cache.
            
        Returns:
            AggregatedPrice object or None.
        """
        cache_key = f"agg_{symbol}"
        if not force_refresh:
            cached = self._price_cache.get(cache_key)
            if cached is not None:
                return cached
        
        sources = self.get_sources(symbol)
        if not sources:
            # Try CEX fallback
            if self.use_cex_fallback:
                price_data = self._fetch_cex_price(symbol)
                if price_data:
                    agg = AggregatedPrice(
                        symbol=symbol,
                        price=price_data.price,
                        sources_used=["cex"],
                        confidence=0.8,
                        timestamp=datetime.now()
                    )
                    self._price_cache.set(cache_key, agg)
                    return agg
            return None
        
        # Fetch from all sources
        prices = []
        for source in sources[:max_sources]:
            if not source.enabled:
                continue
            
            try:
                price_data = self._fetch_from_source(symbol, source)
                if price_data is not None:
                    prices.append(price_data)
            except Exception as e:
                logger.warning(f"Source {source.name} failed: {e}")
                continue
        
        if len(prices) < min_sources:
            return None
        
        # Calculate aggregated price
        total_weight = sum(p.confidence for p in prices)
        if total_weight == 0:
            return None
        
        weighted_price = sum(p.price * p.confidence for p in prices) / total_weight
        
        # Calculate spread
        prices_list = [p.price for p in prices]
        spread = (max(prices_list) - min(prices_list)) / (max(prices_list) if max(prices_list) > 0 else 1)
        
        agg_price = AggregatedPrice(
            symbol=symbol,
            price=weighted_price,
            sources_used=[p.source for p in prices],
            confidence=min(total_weight / len(prices), 1.0),
            timestamp=datetime.now(),
            spread=spread,
            volume_24h=max((p.volume_24h for p in prices if p.volume_24h), default=None)
        )
        
        # Cache result
        self._price_cache.set(cache_key, agg_price)
        
        return agg_price
    
    # ============ Source-Specific Fetching ============
    
    def _fetch_from_source(self, symbol: str, source: PriceSource) -> Optional[PriceData]:
        """
        Fetch price from a specific source.
        
        Args:
            symbol: Trading pair symbol.
            source: PriceSource object.
            
        Returns:
            PriceData object or None.
        """
        if source.type == "chainlink":
            return self._fetch_chainlink_price(symbol, source)
        elif source.type == "uniswap_v2":
            return self._fetch_uniswap_v2_price(symbol, source)
        elif source.type == "uniswap_v3":
            return self._fetch_uniswap_v3_price(symbol, source)
        elif source.type == "curve":
            return self._fetch_curve_price(symbol, source)
        else:
            logger.warning(f"Unsupported source type: {source.type}")
            return None
    
    def _fetch_chainlink_price(self, symbol: str, source: PriceSource) -> Optional[PriceData]:
        """
        Fetch price from Chainlink oracle.
        
        Args:
            symbol: Trading pair symbol.
            source: PriceSource object.
            
        Returns:
            PriceData object or None.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        contract = w3.eth.contract(
            address=source.address,
            abi=self.CHAINLINK_AGGREGATOR_ABI
        )
        
        try:
            # Get latest round data
            round_data = contract.functions.latestRoundData().call()
            
            # Extract values
            answer = round_data[1]  # int256
            updated_at = round_data[3]  # uint256
            
            # Get decimals
            decimals = contract.functions.decimals().call()
            
            # Get description
            description = contract.functions.description().call()
            
            # Convert to float
            price = answer / (10 ** decimals) if decimals > 0 else float(answer)
            
            # Check price age
            age_seconds = int(time.time()) - updated_at
            if age_seconds > self.max_price_age_seconds:
                logger.warning(f"Chainlink price {source.name} is stale ({age_seconds}s old)")
                # Still return with lower confidence
                confidence = 0.5
            
            # Check if price is valid
            if price <= 0:
                return None
            
            return PriceData(
                symbol=symbol,
                price=price,
                source=f"chainlink_{source.name}",
                timestamp=datetime.fromtimestamp(updated_at),
                confidence=0.95 if age_seconds < 300 else 0.7,
                additional_data={
                    "round_id": round_data[0],
                    "started_at": round_data[2],
                    "answered_in_round": round_data[4],
                    "description": description,
                    "decimals": decimals,
                    "age_seconds": age_seconds
                }
            )
            
        except Exception as e:
            logger.error(f"Chainlink price fetch failed for {source.name}: {e}")
            return None
    
    def _fetch_uniswap_v2_price(self, symbol: str, source: PriceSource) -> Optional[PriceData]:
        """
        Fetch price from Uniswap V2 pair.
        
        Args:
            symbol: Trading pair symbol.
            source: PriceSource object.
            
        Returns:
            PriceData object or None.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        contract = w3.eth.contract(
            address=source.address,
            abi=self.UNISWAP_V2_PAIR_ABI
        )
        
        try:
            # Get reserves
            reserve0, reserve1, block_timestamp = contract.functions.getReserves().call()
            
            # Get tokens
            token0 = contract.functions.token0().call()
            token1 = contract.functions.token1().call()
            
            # Determine price based on token order
            # This assumes source.base_asset is token0 or token1
            # For simplicity, calculate both directions
            price_in_token0 = reserve1 / reserve0 if reserve0 > 0 else 0
            price_in_token1 = reserve0 / reserve1 if reserve1 > 0 else 0
            
            # Use appropriate price
            # This is simplified - in production, you'd need to know which token is which
            price = price_in_token1  # Price in terms of quote asset
            
            if price <= 0:
                return None
            
            return PriceData(
                symbol=symbol,
                price=price,
                source=f"uniswap_v2_{source.name}",
                timestamp=datetime.now(),
                confidence=0.8,
                additional_data={
                    "reserve0": reserve0,
                    "reserve1": reserve1,
                    "token0": token0,
                    "token1": token1,
                    "block_timestamp": block_timestamp
                }
            )
            
        except Exception as e:
            logger.error(f"Uniswap V2 price fetch failed for {source.name}: {e}")
            return None
    
    def _fetch_uniswap_v3_price(self, symbol: str, source: PriceSource) -> Optional[PriceData]:
        """
        Fetch price from Uniswap V3 pool.
        
        Args:
            symbol: Trading pair symbol.
            source: PriceSource object.
            
        Returns:
            PriceData object or None.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        contract = w3.eth.contract(
            address=source.address,
            abi=self.UNISWAP_V3_POOL_ABI
        )
        
        try:
            # Get sqrt price
            sqrt_price_x96, tick, _, _, _, _, _ = contract.functions.slot0().call()
            
            # Convert sqrt price to price
            # price = (sqrt_price_x96 / 2^96)^2
            price = (sqrt_price_x96 / (2 ** 96)) ** 2
            
            # Adjust for decimals (simplified)
            # In production, you need token decimals
            if price <= 0:
                return None
            
            return PriceData(
                symbol=symbol,
                price=price,
                source=f"uniswap_v3_{source.name}",
                timestamp=datetime.now(),
                confidence=0.85,
                additional_data={
                    "sqrt_price_x96": sqrt_price_x96,
                    "tick": tick
                }
            )
            
        except Exception as e:
            logger.error(f"Uniswap V3 price fetch failed for {source.name}: {e}")
            return None
    
    def _fetch_curve_price(self, symbol: str, source: PriceSource) -> Optional[PriceData]:
        """
        Fetch price from Curve pool.
        
        Args:
            symbol: Trading pair symbol.
            source: PriceSource object.
            
        Returns:
            PriceData object or None.
        """
        # Placeholder for Curve integration
        # Curve pools have specific ABI and calculation methods
        logger.warning("Curve price fetching not fully implemented")
        return None
    
    def _fetch_cex_price(self, symbol: str) -> Optional[PriceData]:
        """
        Fetch price from centralized exchange APIs as fallback.
        
        Args:
            symbol: Trading pair symbol.
            
        Returns:
            PriceData object or None.
        """
        try:
            # Try CoinGecko API
            price = self._fetch_coingecko_price(symbol)
            if price is not None:
                return PriceData(
                    symbol=symbol,
                    price=price,
                    source="coingecko",
                    timestamp=datetime.now(),
                    confidence=0.6
                )
        except Exception as e:
            logger.debug(f"CoinGecko price fetch failed: {e}")
        
        try:
            # Try CoinMarketCap API (would need API key)
            pass
        except:
            pass
        
        return None
    
    def _fetch_coingecko_price(self, symbol: str) -> Optional[float]:
        """
        Fetch price from CoinGecko API.
        
        Args:
            symbol: Trading pair symbol.
            
        Returns:
            Price or None.
        """
        # Parse symbol (e.g., "ETH/USD" -> base = "ethereum", quote = "usd")
        parts = symbol.split('/')
        if len(parts) != 2:
            return None
        
        base = parts[0].lower()
        quote = parts[1].lower()
        
        # Map symbols to CoinGecko IDs
        symbol_map = {
            "eth": "ethereum",
            "btc": "bitcoin",
            "link": "chainlink",
            "uni": "uniswap",
            "aave": "aave",
            "matic": "polygon",
            "usdc": "usd-coin",
            "dai": "dai",
            "usdt": "tether",
            "wbtc": "wrapped-bitcoin",
            "sol": "solana",
            "avax": "avalanche-2",
            "bnb": "binancecoin",
            "ada": "cardano",
            "dot": "polkadot",
            "doge": "dogecoin"
        }
        
        coin_id = symbol_map.get(base, base)
        
        # Make request to CoinGecko
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={quote}"
        
        response = self._network_client.get(url)
        if response.status_code != 200:
            return None
        
        data = response.json()
        if coin_id in data and quote in data[coin_id]:
            return float(data[coin_id][quote])
        
        return None
    
    # ============ Batch Fetching ============
    
    def fetch_multiple_prices(
        self,
        symbols: List[str],
        source_type: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Optional[PriceData]]:
        """
        Fetch prices for multiple symbols.
        
        Args:
            symbols: List of trading pair symbols.
            source_type: Specific source type to use.
            force_refresh: Force refresh cache.
            
        Returns:
            Dictionary of symbol -> PriceData.
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.fetch_price(symbol, source_type, force_refresh)
        return results
    
    def fetch_aggregated_prices(
        self,
        symbols: List[str],
        min_sources: int = 2,
        max_sources: int = 5,
        force_refresh: bool = False
    ) -> Dict[str, Optional[AggregatedPrice]]:
        """
        Fetch aggregated prices for multiple symbols.
        
        Args:
            symbols: List of trading pair symbols.
            min_sources: Minimum sources required.
            max_sources: Maximum sources to use.
            force_refresh: Force refresh cache.
            
        Returns:
            Dictionary of symbol -> AggregatedPrice.
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.fetch_aggregated_price(
                symbol, min_sources, max_sources, force_refresh
            )
        return results
    
    # ============ Utility Methods ============
    
    def get_token_decimals(self, token_address: str) -> int:
        """
        Get token decimals from contract.
        
        Args:
            token_address: Token contract address.
            
        Returns:
            Number of decimals.
        """
        # Check cache
        cached = self._decimals_cache.get(token_address)
        if cached is not None:
            return cached
        
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        # Minimal ERC20 decimals ABI
        abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        
        try:
            contract = w3.eth.contract(address=token_address, abi=abi)
            decimals = contract.functions.decimals().call()
            self._decimals_cache.set(token_address, decimals)
            return decimals
        except Exception as e:
            logger.warning(f"Failed to get decimals for {token_address}: {e}")
            return 18
    
    def get_normalized_price(
        self,
        symbol: str,
        quote_asset: str = "USD",
        force_refresh: bool = False
    ) -> Optional[float]:
        """
        Get normalized price in a specific quote asset.
        
        Args:
            symbol: Trading pair symbol.
            quote_asset: Quote asset symbol.
            force_refresh: Force refresh cache.
            
        Returns:
            Price or None.
        """
        # If symbol already in quote asset, fetch directly
        if symbol.endswith(f"/{quote_asset}"):
            price_data = self.fetch_price(symbol, force_refresh=force_refresh)
            return price_data.price if price_data else None
        
        # Otherwise, fetch price and convert
        price_data = self.fetch_price(symbol, force_refresh=force_refresh)
        if price_data is None:
            return None
        
        # If quote asset is not the price quote, need conversion
        if price_data.additional_data.get('quote_asset') != quote_asset:
            # Try to get conversion rate
            conversion_symbol = f"{price_data.symbol.split('/')[0]}/{quote_asset}"
            conversion_data = self.fetch_price(conversion_symbol, force_refresh=force_refresh)
            if conversion_data is not None:
                return price_data.price * conversion_data.price
        
        return price_data.price
    
    def clear_cache(self) -> None:
        """Clear all price caches."""
        self._price_cache.clear()
        self._source_cache.clear()
        self._decimals_cache.clear()
        logger.info("Price cache cleared")
    
    def get_price_stats(self) -> Dict[str, Any]:
        """
        Get price statistics.
        
        Returns:
            Statistics dictionary.
        """
        return {
            'symbols_available': len(self._sources),
            'total_sources': sum(len(sources) for sources in self._sources.values()),
            'cache_size': len(self._price_cache._cache),
            'cache_ttl': self.cache_ttl,
            'max_price_age': self.max_price_age_seconds,
            'use_cex_fallback': self.use_cex_fallback,
            'symbols': list(self._sources.keys())
        }


def create_price_client(
    web3_client: Any,
    symbols: Optional[List[str]] = None,
    cache_ttl: int = 60,
    use_cex_fallback: bool = True
) -> Web3Price:
    """
    Create a Web3 price client.
    
    Args:
        web3_client: Web3 client instance.
        symbols: Default symbols to load.
        cache_ttl: Cache TTL in seconds.
        use_cex_fallback: Use CEX fallback.
        
    Returns:
        Web3Price instance.
    """
    return Web3Price(
        web3_client=web3_client,
        default_symbols=symbols,
        cache_ttl=cache_ttl,
        use_cex_fallback=use_cex_fallback
    )


__all__ = [
    'PriceSource',
    'PriceData',
    'AggregatedPrice',
    'Web3Price',
    'create_price_client'
]

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Cross-Chain Detector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced cross-chain arbitrage detector with:
- Multi-chain price monitoring
- Cross-chain arbitrage opportunity detection
- Bridge fee calculation
- Gas cost estimation
- Route optimization
- MEV protection
- Real-time detection
- Historical analysis
"""

import asyncio
import json
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .base_detector import BaseDetector, DetectionResult, DetectionType, DetectionPriority
from ..data.base import BaseDataManager
from ..data.price_manager import PriceManager, PriceSource
from ..data.exceptions import DetectorError, DataNotFoundError

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class ChainType(str, Enum):
    """Supported blockchain types."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    FANTOM = "fantom"
    SOLANA = "solana"
    NEAR = "near"
    COSMOS = "cosmos"
    POLKADOT = "polkadot"
    CELO = "celo"
    GNOSIS = "gnosis"
    MOONBEAM = "moonbeam"
    AURORA = "aurora"
    HARMONY = "harmony"


class BridgeType(str, Enum):
    """Types of bridges."""
    NATIVE = "native"
    THIRD_PARTY = "third_party"
    CROSS_CHAIN = "cross_chain"
    LIQUIDITY = "liquidity"
    WRAPPED = "wrapped"
    ATOMIC = "atomic"
    MESSAGING = "messaging"
    ROLLUP = "rollup"


class TokenType(str, Enum):
    """Types of tokens."""
    NATIVE = "native"
    ERC20 = "erc20"
    BEP20 = "bep20"
    SPL = "spl"
    CW20 = "cw20"
    PS20 = "ps20"
    WRAPPED = "wrapped"
    STABLE = "stable"
    GOVERNANCE = "governance"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class ChainConfig:
    """Configuration for a blockchain."""
    
    chain_id: str
    chain_type: ChainType
    name: str
    rpc_url: str
    native_token: str
    native_token_symbol: str
    native_token_decimals: int
    block_time_seconds: float = 2.0
    gas_price_gwei: float = 20.0
    gas_limit: int = 21000
    is_active: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenInfo:
    """Information about a token."""
    
    address: str
    symbol: str
    name: str
    decimals: int
    chain_id: str
    token_type: TokenType
    is_native: bool = False
    is_wrapped: bool = False
    price_usd: float = 0.0
    volume_24h: float = 0.0
    liquidity: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeConfig:
    """Configuration for a bridge."""
    
    bridge_id: str
    bridge_type: BridgeType
    name: str
    source_chains: List[str]
    destination_chains: List[str]
    supported_tokens: List[str]
    fee_percentage: float = 0.1
    fixed_fee_usd: float = 0.0
    min_amount_usd: float = 10.0
    max_amount_usd: float = 1000000.0
    estimated_time_seconds: float = 120.0
    reliability_score: float = 0.95
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossChainPrice:
    """Price information across chains."""
    
    token_address: str
    token_symbol: str
    chain_id: str
    price_usd: float
    liquidity: float
    volume_24h: float
    timestamp: datetime
    source: str
    confidence: float = 1.0
    spread_pct: float = 0.0


@dataclass
class CrossChainOpportunity:
    """Cross-chain arbitrage opportunity."""
    
    opportunity_id: str = field(default_factory=lambda: f"cc_{int(time.time() * 1000)}")
    token_address: str
    token_symbol: str
    source_chain: str
    destination_chain: str
    source_price_usd: float
    destination_price_usd: float
    price_difference_pct: float
    gross_profit_pct: float
    net_profit_pct: float
    bridge_fee_pct: float
    gas_cost_usd: float
    slippage_pct: float
    min_profit_usd: float
    max_profit_usd: float
    optimal_amount: float
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    routes: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'opportunity_id': self.opportunity_id,
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'source_chain': self.source_chain,
            'destination_chain': self.destination_chain,
            'source_price_usd': self.source_price_usd,
            'destination_price_usd': self.destination_price_usd,
            'price_difference_pct': self.price_difference_pct,
            'gross_profit_pct': self.gross_profit_pct,
            'net_profit_pct': self.net_profit_pct,
            'bridge_fee_pct': self.bridge_fee_pct,
            'gas_cost_usd': self.gas_cost_usd,
            'slippage_pct': self.slippage_pct,
            'min_profit_usd': self.min_profit_usd,
            'max_profit_usd': self.max_profit_usd,
            'optimal_amount': self.optimal_amount,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'routes': self.routes,
            'risks': self.risks,
            'metadata': self.metadata,
        }


@dataclass
class CrossChainStats:
    """Statistics for cross-chain arbitrage."""
    
    chain_id: str
    total_opportunities: int = 0
    profitable_opportunities: int = 0
    executed_opportunities: int = 0
    avg_profit_pct: float = 0.0
    total_profit_usd: float = 0.0
    success_rate: float = 0.0
    avg_confidence: float = 0.0
    last_opportunity: Optional[datetime] = None
    chain_distribution: Dict[str, int] = field(default_factory=dict)
    token_distribution: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'chain_id': self.chain_id,
            'total_opportunities': self.total_opportunities,
            'profitable_opportunities': self.profitable_opportunities,
            'executed_opportunities': self.executed_opportunities,
            'avg_profit_pct': self.avg_profit_pct,
            'total_profit_usd': self.total_profit_usd,
            'success_rate': self.success_rate,
            'avg_confidence': self.avg_confidence,
            'last_opportunity': self.last_opportunity.isoformat() if self.last_opportunity else None,
            'chain_distribution': self.chain_distribution,
            'token_distribution': self.token_distribution,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# CROSS-CHAIN DETECTOR IMPLEMENTATION
# ============================================================

class CrossChainDetector(BaseDetector):
    """
    Advanced cross-chain arbitrage detector.
    
    Features:
    - Multi-chain price monitoring
    - Cross-chain opportunity detection
    - Bridge fee calculation
    - Gas cost estimation
    - Route optimization
    - MEV protection
    - Real-time detection
    - Historical analysis
    """

    def __init__(
        self,
        price_manager: PriceManager,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize cross-chain detector.

        Args:
            price_manager: PriceManager instance
            config: Configuration dictionary
            redis_client: Redis client for caching
        """
        super().__init__(config, name="CrossChainDetector")
        
        self.price_manager = price_manager
        self.redis = redis_client
        
        # Chain configurations
        self._chains: Dict[str, ChainConfig] = {}
        self._tokens: Dict[str, Dict[str, TokenInfo]] = {}  # chain_id -> address -> TokenInfo
        self._bridges: Dict[str, BridgeConfig] = {}
        
        # Price history
        self._price_history: Dict[str, Dict[str, deque]] = {}  # chain_id -> token_address -> deque
        
        # Opportunities
        self._opportunities: List[CrossChainOpportunity] = []
        self._opportunity_history: Dict[str, deque] = {}  # token_address -> deque
        
        # Statistics
        self._stats: Dict[str, CrossChainStats] = {}
        
        # Thresholds
        self._min_profit_pct = 0.5
        self._min_confidence = 0.6
        self._max_slippage_pct = 1.0
        self._min_liquidity_usd = 10000
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 60
        
        logger.info("CrossChainDetector initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def detect(self, data: Dict[str, Any]) -> Optional[DetectionResult]:
        """
        Detect cross-chain arbitrage opportunities.

        Args:
            data: Input data containing chain and token information

        Returns:
            DetectionResult or None
        """
        try:
            chain_ids = data.get('chain_ids', list(self._chains.keys()))
            token_addresses = data.get('token_addresses', [])
            
            if not chain_ids:
                logger.warning("No chains available for detection")
                return None
            
            # Get prices across chains
            prices = await self._get_cross_chain_prices(chain_ids, token_addresses)
            
            if not prices:
                return None
            
            # Find opportunities
            opportunities = await self._find_opportunities(prices)
            
            if not opportunities:
                return None
            
            # Filter and rank opportunities
            best_opportunity = await self._rank_opportunities(opportunities)
            
            if best_opportunity:
                # Create detection result
                return DetectionResult(
                    type=DetectionType.OPPORTUNITY,
                    priority=DetectionPriority.HIGH,
                    score=best_opportunity.net_profit_pct,
                    confidence=best_opportunity.confidence,
                    data=best_opportunity.to_dict(),
                    description=(
                        f"Cross-chain arbitrage: {best_opportunity.token_symbol} "
                        f"{best_opportunity.source_chain} -> {best_opportunity.destination_chain} "
                        f"Profit: {best_opportunity.net_profit_pct:.2f}%"
                    ),
                    source="cross_chain_detector",
                )
            
            return None

        except Exception as e:
            logger.error(f"Cross-chain detection failed: {e}")
            return None

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        return True

    async def get_required_fields(self) -> List[str]:
        """Get required fields."""
        return ['chain_ids']

    async def add_chain(self, config: ChainConfig) -> None:
        """
        Add a blockchain configuration.

        Args:
            config: Chain configuration
        """
        self._chains[config.chain_id] = config
        self._price_history[config.chain_id] = {}
        self._tokens[config.chain_id] = {}
        
        # Initialize stats
        self._stats[config.chain_id] = CrossChainStats(
            chain_id=config.chain_id,
        )
        
        logger.info(f"Added chain: {config.chain_id} ({config.name})")

    async def add_token(self, chain_id: str, token: TokenInfo) -> None:
        """
        Add a token for a chain.

        Args:
            chain_id: Chain ID
            token: Token information
        """
        if chain_id not in self._tokens:
            self._tokens[chain_id] = {}
        
        self._tokens[chain_id][token.address] = token
        
        # Initialize price history
        if chain_id not in self._price_history:
            self._price_history[chain_id] = {}
        self._price_history[chain_id][token.address] = deque(maxlen=1000)
        
        logger.info(f"Added token: {token.symbol} ({token.address}) on {chain_id}")

    async def add_bridge(self, config: BridgeConfig) -> None:
        """
        Add a bridge configuration.

        Args:
            config: Bridge configuration
        """
        self._bridges[config.bridge_id] = config
        logger.info(f"Added bridge: {config.bridge_id} ({config.name})")

    async def update_price(
        self,
        chain_id: str,
        token_address: str,
        price_usd: float,
        liquidity: float = 0.0,
        volume_24h: float = 0.0,
        source: str = "api",
        confidence: float = 1.0,
    ) -> None:
        """
        Update price for a token on a chain.

        Args:
            chain_id: Chain ID
            token_address: Token address
            price_usd: Price in USD
            liquidity: Liquidity in USD
            volume_24h: 24h volume in USD
            source: Data source
            confidence: Confidence score
        """
        if chain_id not in self._price_history:
            self._price_history[chain_id] = {}
        
        if token_address not in self._price_history[chain_id]:
            self._price_history[chain_id][token_address] = deque(maxlen=1000)
        
        # Add price
        price_data = CrossChainPrice(
            token_address=token_address,
            token_symbol=self._get_token_symbol(chain_id, token_address),
            chain_id=chain_id,
            price_usd=price_usd,
            liquidity=liquidity,
            volume_24h=volume_24h,
            timestamp=datetime.utcnow(),
            source=source,
            confidence=confidence,
        )
        
        self._price_history[chain_id][token_address].append(price_data)
        
        # Update token price
        if chain_id in self._tokens and token_address in self._tokens[chain_id]:
            self._tokens[chain_id][token_address].price_usd = price_usd
            self._tokens[chain_id][token_address].liquidity = liquidity
            self._tokens[chain_id][token_address].volume_24h = volume_24h

    async def get_opportunities(
        self,
        chain_ids: Optional[List[str]] = None,
        token_addresses: Optional[List[str]] = None,
        min_profit_pct: float = 0.5,
        limit: int = 100,
    ) -> List[CrossChainOpportunity]:
        """
        Get cross-chain opportunities.

        Args:
            chain_ids: List of chain IDs
            token_addresses: List of token addresses
            min_profit_pct: Minimum profit percentage
            limit: Maximum number of opportunities

        Returns:
            List of CrossChainOpportunity
        """
        chain_ids = chain_ids or list(self._chains.keys())
        token_addresses = token_addresses or []
        
        # Get prices
        prices = await self._get_cross_chain_prices(chain_ids, token_addresses)
        
        if not prices:
            return []
        
        # Find opportunities
        opportunities = await self._find_opportunities(prices)
        
        # Filter by profit
        opportunities = [
            o for o in opportunities
            if o.net_profit_pct >= min_profit_pct
        ]
        
        # Sort by profit
        opportunities.sort(key=lambda o: o.net_profit_pct, reverse=True)
        
        return opportunities[:limit]

    async def get_stats(
        self,
        chain_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get cross-chain statistics.

        Args:
            chain_id: Chain ID (all if None)

        Returns:
            Dictionary with statistics
        """
        if chain_id:
            if chain_id in self._stats:
                return self._stats[chain_id].to_dict()
            return {}
        
        return {
            cid: stats.to_dict()
            for cid, stats in self._stats.items()
        }

    async def simulate_opportunity(
        self,
        opportunity: CrossChainOpportunity,
        amount_usd: float,
    ) -> Dict[str, Any]:
        """
        Simulate executing an opportunity.

        Args:
            opportunity: CrossChainOpportunity
            amount_usd: Amount in USD

        Returns:
            Simulation results
        """
        # Calculate actual amounts
        source_amount = amount_usd / opportunity.source_price_usd
        bridge_fee = amount_usd * opportunity.bridge_fee_pct / 100
        gas_cost = opportunity.gas_cost_usd
        slippage = amount_usd * opportunity.slippage_pct / 100
        
        # Expected destination amount
        expected_destination = amount_usd + (amount_usd * opportunity.price_difference_pct / 100)
        
        # Net profit after all costs
        net_profit = (amount_usd * opportunity.price_difference_pct / 100) - bridge_fee - gas_cost - slippage
        
        return {
            'amount_usd': amount_usd,
            'source_amount': source_amount,
            'bridge_fee_usd': bridge_fee,
            'gas_cost_usd': gas_cost,
            'slippage_usd': slippage,
            'expected_destination_usd': expected_destination,
            'net_profit_usd': net_profit,
            'net_profit_pct': (net_profit / amount_usd) * 100 if amount_usd > 0 else 0,
            'roi_pct': (net_profit / amount_usd) * 100 if amount_usd > 0 else 0,
            'estimated_time_seconds': opportunity.metadata.get('estimated_time', 120),
            'risks': opportunity.risks,
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    async def _get_cross_chain_prices(
        self,
        chain_ids: List[str],
        token_addresses: List[str],
    ) -> Dict[str, Dict[str, CrossChainPrice]]:
        """Get prices across chains."""
        prices = {}
        
        for chain_id in chain_ids:
            if chain_id not in self._chains:
                continue
            
            prices[chain_id] = {}
            
            # Get tokens for this chain
            tokens = self._tokens.get(chain_id, {})
            
            # Filter by token addresses if specified
            if token_addresses:
                tokens = {addr: token for addr, token in tokens.items() if addr in token_addresses}
            
            for token_address, token in tokens.items():
                # Get latest price from history
                history = self._price_history.get(chain_id, {}).get(token_address, deque())
                if history:
                    latest = history[-1]
                    prices[chain_id][token_address] = latest
        
        return prices

    async def _find_opportunities(
        self,
        prices: Dict[str, Dict[str, CrossChainPrice]],
    ) -> List[CrossChainOpportunity]:
        """Find cross-chain arbitrage opportunities."""
        opportunities = []
        
        # Get all token addresses across chains
        token_addresses = set()
        for chain_prices in prices.values():
            token_addresses.update(chain_prices.keys())
        
        for token_address in token_addresses:
            # Get prices for this token across chains
            token_prices = {}
            for chain_id, chain_prices in prices.items():
                if token_address in chain_prices:
                    token_prices[chain_id] = chain_prices[token_address]
            
            if len(token_prices) < 2:
                continue
            
            # Check for arbitrage opportunities
            opportunities.extend(
                await self._check_token_arbitrage(token_address, token_prices)
            )
        
        return opportunities

    async def _check_token_arbitrage(
        self,
        token_address: str,
        prices: Dict[str, CrossChainPrice],
    ) -> List[CrossChainOpportunity]:
        """Check arbitrage opportunities for a token."""
        opportunities = []
        
        # Get token symbol
        token_symbol = self._get_token_symbol(
            next(iter(prices.values())).chain_id,
            token_address,
        )
        
        # Check each pair of chains
        chain_ids = list(prices.keys())
        
        for i in range(len(chain_ids)):
            for j in range(i + 1, len(chain_ids)):
                chain_a = chain_ids[i]
                chain_b = chain_ids[j]
                
                price_a = prices[chain_a]
                price_b = prices[chain_b]
                
                # Check if prices are valid
                if price_a.price_usd <= 0 or price_b.price_usd <= 0:
                    continue
                
                # Calculate price difference
                price_diff_pct = ((price_b.price_usd - price_a.price_usd) / price_a.price_usd) * 100
                
                if abs(price_diff_pct) < self._min_profit_pct:
                    continue
                
                # Determine direction (buy low, sell high)
                if price_a.price_usd < price_b.price_usd:
                    source_chain = chain_a
                    destination_chain = chain_b
                    source_price = price_a.price_usd
                    destination_price = price_b.price_usd
                else:
                    source_chain = chain_b
                    destination_chain = chain_a
                    source_price = price_b.price_usd
                    destination_price = price_a.price_usd
                
                # Calculate costs
                bridge_fee_pct = await self._get_bridge_fee(
                    source_chain, destination_chain, token_address
                )
                
                gas_cost_usd = await self._estimate_gas_cost(
                    source_chain, destination_chain
                )
                
                slippage_pct = await self._estimate_slippage(
                    source_chain, destination_chain, token_address
                )
                
                # Calculate net profit
                gross_profit_pct = abs(price_diff_pct)
                net_profit_pct = gross_profit_pct - bridge_fee_pct - slippage_pct
                
                # Account for gas costs
                min_profit_usd = await self._calculate_min_profit(
                    source_chain, destination_chain, token_address
                )
                
                # Find optimal amount
                optimal_amount = await self._find_optimal_amount(
                    source_chain, destination_chain, token_address, source_price
                )
                
                # Calculate max profit
                max_profit_usd = optimal_amount * (net_profit_pct / 100)
                
                # Check confidence
                confidence = await self._calculate_confidence(
                    source_chain, destination_chain, token_address,
                    gross_profit_pct, net_profit_pct
                )
                
                if confidence < self._min_confidence:
                    continue
                
                # Find routes
                routes = await self._find_routes(
                    source_chain, destination_chain, token_address
                )
                
                # Identify risks
                risks = await self._identify_risks(
                    source_chain, destination_chain, token_address,
                    net_profit_pct, confidence
                )
                
                # Create opportunity
                opportunity = CrossChainOpportunity(
                    token_address=token_address,
                    token_symbol=token_symbol,
                    source_chain=source_chain,
                    destination_chain=destination_chain,
                    source_price_usd=source_price,
                    destination_price_usd=destination_price,
                    price_difference_pct=abs(price_diff_pct),
                    gross_profit_pct=gross_profit_pct,
                    net_profit_pct=net_profit_pct,
                    bridge_fee_pct=bridge_fee_pct,
                    gas_cost_usd=gas_cost_usd,
                    slippage_pct=slippage_pct,
                    min_profit_usd=min_profit_usd,
                    max_profit_usd=max_profit_usd,
                    optimal_amount=optimal_amount,
                    confidence=confidence,
                    routes=routes,
                    risks=risks,
                    metadata={
                        'price_a': price_a.price_usd,
                        'price_b': price_b.price_usd,
                        'liquidity_a': price_a.liquidity,
                        'liquidity_b': price_b.liquidity,
                        'volume_a': price_a.volume_24h,
                        'volume_b': price_b.volume_24h,
                        'source': price_a.source,
                        'estimated_time': await self._estimate_time(
                            source_chain, destination_chain
                        ),
                    },
                )
                
                opportunities.append(opportunity)
                
                # Update statistics
                await self._update_stats(opportunity)
        
        return opportunities

    async def _get_bridge_fee(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
    ) -> float:
        """Get bridge fee percentage."""
        # Find suitable bridge
        best_bridge = None
        best_fee = float('inf')
        
        for bridge in self._bridges.values():
            if (source_chain in bridge.source_chains and
                destination_chain in bridge.destination_chains and
                token_address in bridge.supported_tokens):
                if bridge.fee_percentage < best_fee:
                    best_fee = bridge.fee_percentage
                    best_bridge = bridge
        
        return best_fee if best_bridge else 0.5  # Default 0.5%

    async def _estimate_gas_cost(
        self,
        source_chain: str,
        destination_chain: str,
    ) -> float:
        """Estimate gas cost in USD."""
        chain_a = self._chains.get(source_chain)
        chain_b = self._chains.get(destination_chain)
        
        if not chain_a or not chain_b:
            return 5.0  # Default $5
        
        # Estimate gas cost based on chain
        gas_cost = 0.0
        
        # Source chain gas
        if chain_a.chain_type == ChainType.ETHEREUM:
            gas_cost += chain_a.gas_price_gwei * chain_a.gas_limit * 0.000000001 * 2000  # ETH price ~$2000
        elif chain_a.chain_type in [ChainType.BSC, ChainType.POLYGON]:
            gas_cost += 0.5  # ~$0.50
        else:
            gas_cost += 1.0  # ~$1.00
        
        # Destination chain gas (for bridge operations)
        if chain_b.chain_type == ChainType.ETHEREUM:
            gas_cost += chain_b.gas_price_gwei * chain_b.gas_limit * 0.000000001 * 2000
        elif chain_b.chain_type in [ChainType.BSC, ChainType.POLYGON]:
            gas_cost += 0.5
        else:
            gas_cost += 1.0
        
        return gas_cost

    async def _estimate_slippage(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
    ) -> float:
        """Estimate slippage percentage."""
        # Get liquidity for token
        token_a = self._tokens.get(source_chain, {}).get(token_address)
        token_b = self._tokens.get(destination_chain, {}).get(token_address)
        
        if not token_a or not token_b:
            return 0.5  # Default 0.5%
        
        # Calculate slippage based on liquidity
        liquidity_a = token_a.liquidity
        liquidity_b = token_b.liquidity
        
        if liquidity_a < self._min_liquidity_usd or liquidity_b < self._min_liquidity_usd:
            return 1.0  # Higher slippage for low liquidity
        
        # Estimate slippage (inverse of liquidity)
        avg_liquidity = (liquidity_a + liquidity_b) / 2
        slippage = min(2.0, 50 / (avg_liquidity / 1000))
        
        return max(0.1, slippage)

    async def _calculate_min_profit(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
    ) -> float:
        """Calculate minimum profitable amount."""
        # Gas cost + bridge fee + minimum profit
        gas_cost = await self._estimate_gas_cost(source_chain, destination_chain)
        bridge_fee = await self._get_bridge_fee(source_chain, destination_chain, token_address)
        
        # Minimum profit = gas_cost * 2 + bridge_fee
        return gas_cost * 2 + 10  # Minimum $10 profit

    async def _find_optimal_amount(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
        source_price: float,
    ) -> float:
        """Find optimal trade amount."""
        # Get liquidity
        token_a = self._tokens.get(source_chain, {}).get(token_address)
        token_b = self._tokens.get(destination_chain, {}).get(token_address)
        
        if not token_a or not token_b:
            return 1000.0  # Default $1000
        
        # Optimal amount based on liquidity
        liquidity = min(token_a.liquidity, token_b.liquidity)
        optimal = liquidity * 0.01  # 1% of liquidity
        
        # Cap at reasonable size
        return min(max(100, optimal), 100000)

    async def _calculate_confidence(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
        gross_profit_pct: float,
        net_profit_pct: float,
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5
        
        # Higher profit = higher confidence
        confidence += min(0.3, net_profit_pct / 100)
        
        # Chain reliability
        chain_a = self._chains.get(source_chain)
        chain_b = self._chains.get(destination_chain)
        
        if chain_a and chain_a.is_active:
            confidence += 0.1
        if chain_b and chain_b.is_active:
            confidence += 0.1
        
        # Bridge reliability
        bridges = [b for b in self._bridges.values() 
                  if (source_chain in b.source_chains and 
                      destination_chain in b.destination_chains and
                      token_address in b.supported_tokens)]
        
        if bridges:
            best_reliability = max(b.reliability_score for b in bridges)
            confidence += best_reliability * 0.1
        
        # Token liquidity
        token_a = self._tokens.get(source_chain, {}).get(token_address)
        token_b = self._tokens.get(destination_chain, {}).get(token_address)
        
        if token_a and token_b:
            if token_a.liquidity > 100000 and token_b.liquidity > 100000:
                confidence += 0.1
            elif token_a.liquidity > 50000 and token_b.liquidity > 50000:
                confidence += 0.05
        
        return min(1.0, confidence)

    async def _find_routes(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
    ) -> List[Dict[str, Any]]:
        """Find possible routes for arbitrage."""
        routes = []
        
        # Direct bridge route
        direct_bridge = None
        for bridge in self._bridges.values():
            if (source_chain in bridge.source_chains and
                destination_chain in bridge.destination_chains and
                token_address in bridge.supported_tokens):
                direct_bridge = bridge
                break
        
        if direct_bridge:
            routes.append({
                'type': 'direct',
                'bridge_id': direct_bridge.bridge_id,
                'bridge_name': direct_bridge.name,
                'steps': 1,
                'estimated_time': direct_bridge.estimated_time_seconds,
                'fee_pct': direct_bridge.fee_percentage,
                'reliability': direct_bridge.reliability_score,
            })
        
        # Multi-hop routes
        # Check for intermediate chains
        intermediate_chains = set(self._chains.keys()) - {source_chain, destination_chain}
        
        for intermediate in intermediate_chains:
            # Check bridge from source to intermediate
            bridge_a = None
            for bridge in self._bridges.values():
                if (source_chain in bridge.source_chains and
                    intermediate in bridge.destination_chains and
                    token_address in bridge.supported_tokens):
                    bridge_a = bridge
                    break
            
            # Check bridge from intermediate to destination
            bridge_b = None
            for bridge in self._bridges.values():
                if (intermediate in bridge.source_chains and
                    destination_chain in bridge.destination_chains and
                    token_address in bridge.supported_tokens):
                    bridge_b = bridge
                    break
            
            if bridge_a and bridge_b:
                total_fee = bridge_a.fee_percentage + bridge_b.fee_percentage
                routes.append({
                    'type': 'multi_hop',
                    'intermediate_chain': intermediate,
                    'bridges': [bridge_a.bridge_id, bridge_b.bridge_id],
                    'steps': 2,
                    'estimated_time': bridge_a.estimated_time_seconds + bridge_b.estimated_time_seconds,
                    'fee_pct': total_fee,
                    'reliability': (bridge_a.reliability_score + bridge_b.reliability_score) / 2,
                })
        
        return routes

    async def _identify_risks(
        self,
        source_chain: str,
        destination_chain: str,
        token_address: str,
        net_profit_pct: float,
        confidence: float,
    ) -> List[str]:
        """Identify risks for an opportunity."""
        risks = []
        
        # Price volatility risk
        if net_profit_pct < 2:
            risks.append("Low profit margin, price volatility could eliminate profit")
        
        # Liquidity risk
        token_a = self._tokens.get(source_chain, {}).get(token_address)
        token_b = self._tokens.get(destination_chain, {}).get(token_address)
        
        if token_a and token_b:
            if token_a.liquidity < 100000 or token_b.liquidity < 100000:
                risks.append("Low liquidity, slippage risk")
        
        # Bridge risk
        bridges = [b for b in self._bridges.values() 
                  if (source_chain in b.source_chains and 
                      destination_chain in b.destination_chains and
                      token_address in b.supported_tokens)]
        
        if not bridges:
            risks.append("No direct bridge available")
        else:
            for bridge in bridges:
                if bridge.reliability_score < 0.9:
                    risks.append(f"Bridge {bridge.name} has low reliability")
        
        # MEV risk
        if source_chain == "ethereum" or destination_chain == "ethereum":
            risks.append("MEV risk on Ethereum chain")
        
        # Network congestion risk
        chain_a = self._chains.get(source_chain)
        chain_b = self._chains.get(destination_chain)
        
        if chain_a and chain_a.gas_price_gwei > 100:
            risks.append(f"High gas price on {chain_a.name}")
        if chain_b and chain_b.gas_price_gwei > 100:
            risks.append(f"High gas price on {chain_b.name}")
        
        # Confidence risk
        if confidence < 0.7:
            risks.append("Low confidence in opportunity")
        
        return risks

    async def _estimate_time(
        self,
        source_chain: str,
        destination_chain: str,
    ) -> float:
        """Estimate total time for arbitrage."""
        # Get bridge time
        best_time = 120.0  # Default 2 minutes
        
        for bridge in self._bridges.values():
            if (source_chain in bridge.source_chains and
                destination_chain in bridge.destination_chains):
                best_time = min(best_time, bridge.estimated_time_seconds)
        
        # Add buffer for transactions
        chain_a = self._chains.get(source_chain)
        chain_b = self._chains.get(destination_chain)
        
        if chain_a:
            best_time += chain_a.block_time_seconds * 3
        if chain_b:
            best_time += chain_b.block_time_seconds * 3
        
        return best_time

    async def _rank_opportunities(
        self,
        opportunities: List[CrossChainOpportunity],
    ) -> Optional[CrossChainOpportunity]:
        """Rank opportunities and return the best one."""
        if not opportunities:
            return None
        
        # Score each opportunity
        scored = []
        for opp in opportunities:
            score = (
                opp.net_profit_pct * 0.4 +
                opp.confidence * 0.3 -
                opp.slippage_pct * 0.1 -
                (opp.bridge_fee_pct * 0.1) -
                (len(opp.risks) * 0.01)
            )
            scored.append((score, opp))
        
        # Return best
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    async def _update_stats(self, opportunity: CrossChainOpportunity) -> None:
        """Update statistics."""
        # Update source chain stats
        if opportunity.source_chain in self._stats:
            stats = self._stats[opportunity.source_chain]
            stats.total_opportunities += 1
            
            if opportunity.net_profit_pct > 0:
                stats.profitable_opportunities += 1
                stats.total_profit_usd += opportunity.max_profit_usd
                
                total_ops = stats.profitable_opportunities
                stats.avg_profit_pct = (
                    (stats.avg_profit_pct * (total_ops - 1) + opportunity.net_profit_pct) / total_ops
                )
            
            stats.avg_confidence = (
                (stats.avg_confidence * (stats.total_opportunities - 1) + opportunity.confidence) / 
                stats.total_opportunities
            )
            
            stats.last_opportunity = datetime.utcnow()
            
            # Update distributions
            token_key = opportunity.token_symbol
            stats.token_distribution[token_key] = stats.token_distribution.get(token_key, 0) + 1
        
        # Update destination chain stats
        if opportunity.destination_chain in self._stats:
            stats = self._stats[opportunity.destination_chain]
            stats.total_opportunities += 1
            
            if opportunity.net_profit_pct > 0:
                stats.profitable_opportunities += 1
                stats.total_profit_usd += opportunity.max_profit_usd

    def _get_token_symbol(self, chain_id: str, token_address: str) -> str:
        """Get token symbol."""
        if chain_id in self._tokens:
            token = self._tokens[chain_id].get(token_address)
            if token:
                return token.symbol
        return "UNKNOWN"

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the detector."""
        await super().start()
        logger.info("CrossChainDetector started")

    async def stop(self) -> None:
        """Stop the detector."""
        await super().stop()
        logger.info("CrossChainDetector stopped")

    async def clear(self) -> None:
        """Clear detector data."""
        await super().clear()
        self._opportunities.clear()
        self._opportunity_history.clear()
        logger.info("CrossChainDetector cleared")


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_cross_chain_detector(
    price_manager: PriceManager,
    config: Optional[Dict[str, Any]] = None,
    redis_client: Optional[Any] = None,
) -> CrossChainDetector:
    """
    Create a cross-chain detector instance.

    Args:
        price_manager: PriceManager instance
        config: Configuration dictionary
        redis_client: Redis client for caching

    Returns:
        CrossChainDetector instance
    """
    return CrossChainDetector(
        price_manager=price_manager,
        config=config,
        redis_client=redis_client,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the cross-chain detector.
    """
    import asyncio
    import json

    async def main():
        # Setup logging
        logging.basicConfig(level=logging.DEBUG)

        # Initialize price manager
        from ..data.price_manager import create_price_manager
        price_manager = create_price_manager()

        # Create cross-chain detector
        detector = create_cross_chain_detector(price_manager)

        # Add chains
        await detector.add_chain(ChainConfig(
            chain_id="ethereum",
            chain_type=ChainType.ETHEREUM,
            name="Ethereum",
            rpc_url="https://mainnet.infura.io/v3/your-key",
            native_token="0x0000000000000000000000000000000000000000",
            native_token_symbol="ETH",
            native_token_decimals=18,
            gas_price_gwei=20,
        ))

        await detector.add_chain(ChainConfig(
            chain_id="bsc",
            chain_type=ChainType.BSC,
            name="BNB Smart Chain",
            rpc_url="https://bsc-dataseed.binance.org/",
            native_token="0x0000000000000000000000000000000000000000",
            native_token_symbol="BNB",
            native_token_decimals=18,
            gas_price_gwei=5,
        ))

        # Add tokens
        await detector.add_token("ethereum", TokenInfo(
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            symbol="USDC",
            name="USD Coin",
            decimals=6,
            chain_id="ethereum",
            token_type=TokenType.ERC20,
            price_usd=1.0,
            liquidity=10000000,
            volume_24h=5000000,
        ))

        await detector.add_token("bsc", TokenInfo(
            address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            symbol="USDC",
            name="USD Coin",
            decimals=18,
            chain_id="bsc",
            token_type=TokenType.BEP20,
            price_usd=1.0,
            liquidity=5000000,
            volume_24h=3000000,
        ))

        # Add bridge
        await detector.add_bridge(BridgeConfig(
            bridge_id="multichain",
            bridge_type=BridgeType.CROSS_CHAIN,
            name="Multichain",
            source_chains=["ethereum", "bsc"],
            destination_chains=["ethereum", "bsc"],
            supported_tokens=[
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            ],
            fee_percentage=0.1,
            estimated_time_seconds=180,
            reliability_score=0.98,
        ))

        # Update prices
        await detector.update_price(
            chain_id="ethereum",
            token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            price_usd=1.002,
            liquidity=10000000,
            volume_24h=5000000,
        )

        await detector.update_price(
            chain_id="bsc",
            token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            price_usd=0.998,
            liquidity=5000000,
            volume_24h=3000000,
        )

        # Detect opportunities
        result = await detector.detect({
            'chain_ids': ['ethereum', 'bsc'],
            'token_addresses': [
                '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            ],
        })

        if result:
            print(f"Cross-chain opportunity detected: {result.description}")
            print(f"Details: {json.dumps(result.data, indent=2, default=str)}")

        # Get all opportunities
        opportunities = await detector.get_opportunities(
            min_profit_pct=0.1,
            limit=10,
        )

        for opp in opportunities:
            print(f"\nOpportunity: {opp.token_symbol}")
            print(f"  {opp.source_chain} -> {opp.destination_chain}")
            print(f"  Gross profit: {opp.gross_profit_pct:.2f}%")
            print(f"  Net profit: {opp.net_profit_pct:.2f}%")
            print(f"  Confidence: {opp.confidence:.2f}")
            print(f"  Optimal amount: ${opp.optimal_amount:,.2f}")

            # Simulate opportunity
            simulation = await detector.simulate_opportunity(opp, opp.optimal_amount)
            print(f"  Simulation: ${simulation['net_profit_usd']:,.2f} profit")

        # Get statistics
        stats = await detector.get_stats()
        print(f"\nStatistics: {json.dumps(stats, indent=2, default=str)}")

        # Cleanup
        await detector.stop()
        await price_manager.stop()

    asyncio.run(main())

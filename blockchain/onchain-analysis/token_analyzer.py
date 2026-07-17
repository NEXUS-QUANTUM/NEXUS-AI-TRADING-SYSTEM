# blockchain/onchain-analysis/token_analyzer.py
# NEXUS AI TRADING SYSTEM - Advanced Token Analysis Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Comprehensive token analysis engine for on-chain data.
Provides deep analysis of ERC-20 tokens including supply dynamics,
holder distribution, trading patterns, and risk assessment.
"""

import asyncio
import json
import logging
import math
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aiohttp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from web3 import Web3
from web3.contract import Contract

# NEXUS Imports
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.token_analyzer")


# ============================================================================
# Enums & Constants
# ============================================================================

class TokenStandard(str, Enum):
    """Token standards supported."""
    ERC20 = "ERC20"
    ERC721 = "ERC721"
    ERC1155 = "ERC1155"
    BEP20 = "BEP20"
    SPL = "SPL"
    CUSTOM = "custom"


class TokenType(str, Enum):
    """Types of tokens."""
    UTILITY = "utility"
    GOVERNANCE = "governance"
    SECURITY = "security"
    STABLE = "stable"
    MEME = "meme"
    DEFI = "defi"
    GAMING = "gaming"
    NFT = "nft"
    LAYER1 = "layer1"
    LAYER2 = "layer2"
    BRIDGE = "bridge"
    WRAPPED = "wrapped"
    SYNTHETIC = "synthetic"
    LP = "lp"


class TokenRiskLevel(str, Enum):
    """Risk levels for tokens."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"
    SCAM = "scam"


class TokenStatus(str, Enum):
    """Status of a token."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELISTED = "delisted"
    BURNED = "burned"
    MIGRATED = "migrated"


@dataclass
class TokenInfo:
    """Basic token information."""
    address: str
    chain: str
    name: str
    symbol: str
    decimals: int
    standard: TokenStandard
    type: Optional[TokenType] = None
    total_supply: float = 0.0
    circulating_supply: float = 0.0
    max_supply: Optional[float] = None
    holders: int = 0
    created_at: Optional[datetime] = None
    owner: Optional[str] = None
    proxy: Optional[str] = None
    implementation: Optional[str] = None
    is_verified: bool = False
    is_audited: bool = False
    status: TokenStatus = TokenStatus.ACTIVE
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    discord: Optional[str] = None
    github: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenSupply:
    """Token supply information."""
    total_supply: float
    circulating_supply: float
    max_supply: Optional[float] = None
    burned_supply: float = 0.0
    locked_supply: float = 0.0
    staked_supply: float = 0.0
    treasury_supply: float = 0.0
    team_supply: float = 0.0
    public_supply: float = 0.0
    distribution: Dict[str, float] = field(default_factory=dict)
    vesting_schedule: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TokenHolder:
    """Token holder information."""
    address: str
    balance: float
    balance_usd: float
    percentage: float
    rank: int
    first_seen: Optional[datetime] = None
    last_transaction: Optional[datetime] = None
    transaction_count: int = 0
    is_contract: bool = False
    is_exchange: bool = False
    is_whale: bool = False
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenTransaction:
    """Token transaction information."""
    hash: str
    from_address: str
    to_address: str
    amount: float
    amount_usd: float
    price: float
    timestamp: datetime
    block_number: int
    gas_price: float
    gas_used: int
    transaction_type: str
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenTradingInfo:
    """Token trading information."""
    price: float
    price_change_24h: float
    price_change_7d: float
    volume_24h: float
    volume_change_24h: float
    liquidity: float
    market_cap: float
    fully_diluted_valuation: float
    circulating_supply: float
    total_supply: float
    holders: int
    exchanges: List[Dict[str, Any]]
    pairs: List[Dict[str, Any]]
    order_books: Dict[str, Any]
    volatility: float
    spread: float
    depth: float


@dataclass
class TokenRiskAnalysis:
    """Token risk analysis."""
    risk_level: TokenRiskLevel
    risk_score: float
    factors: List[Dict[str, Any]]
    warnings: List[str]
    recommendations: List[str]
    detailed_analysis: Dict[str, Any]
    confidence: float


# ============================================================================
# Core Token Analyzer
# ============================================================================

class TokenAnalyzer:
    """
    Advanced token analysis engine for on-chain data.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Cache
        self._token_cache: Dict[str, TokenInfo] = {}
        self._token_supply_cache: Dict[str, TokenSupply] = {}
        self._token_holders_cache: Dict[str, List[TokenHolder]] = {}
        self._token_transactions_cache: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

        # State
        self._running = False
        self._lock = asyncio.Lock()

        # Performance metrics
        self._performance = {
            "tokens_analyzed": 0,
            "holders_analyzed": 0,
            "transactions_processed": 0,
            "avg_analysis_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # ERC-20 ABI (minimal)
        self._erc20_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
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
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
        ]

        logger.info(
            "TokenAnalyzer initialized",
            extra={"chain": web3_client.chain_name}
        )

    # -----------------------------------------------------------------------
    # Token Information
    # -----------------------------------------------------------------------

    async def get_token_info(
        self,
        token_address: str,
        force_refresh: bool = False
    ) -> Optional[TokenInfo]:
        """Get comprehensive token information."""
        token_address = Web3.to_checksum_address(token_address)

        # Check cache
        if not force_refresh and token_address in self._token_cache:
            self._performance["cache_hits"] += 1
            return self._token_cache[token_address]

        self._performance["cache_misses"] += 1
        start_time = time.time()

        try:
            # Get contract
            contract = self.web3_client.get_contract(
                token_address,
                abi=self._erc20_abi
            )

            # Basic token info
            name = await self._call_contract_function(contract, "name")
            symbol = await self._call_contract_function(contract, "symbol")
            decimals = await self._call_contract_function(contract, "decimals")
            total_supply = await self._call_contract_function(contract, "totalSupply")

            # Get additional info
            info = TokenInfo(
                address=token_address,
                chain=self.web3_client.chain_name,
                name=name or "Unknown",
                symbol=symbol or "UNKNOWN",
                decimals=int(decimals or 18),
                standard=TokenStandard.ERC20,
                total_supply=float(total_supply or 0) / (10 ** int(decimals or 18)),
                is_verified=await self._verify_token(token_address),
                is_audited=await self._check_audit_status(token_address),
            )

            # Try to get holder count
            holders = await self._get_holder_count(token_address)
            info.holders = holders or 0

            # Try to get creation info
            creation_info = await self._get_creation_info(token_address)
            if creation_info:
                info.created_at = creation_info.get("created_at")
                info.owner = creation_info.get("owner")

            # Cache
            self._token_cache[token_address] = info
            self._performance["tokens_analyzed"] += 1

            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["avg_analysis_time_ms"] = (
                (self._performance["avg_analysis_time_ms"] *
                 (self._performance["tokens_analyzed"] - 1) +
                 elapsed_ms) / self._performance["tokens_analyzed"]
            )

            logger.info(
                f"Token info retrieved: {info.symbol}",
                extra={
                    "address": token_address,
                    "name": info.name,
                    "holders": info.holders,
                }
            )

            return info

        except Exception as e:
            logger.error(f"Error getting token info for {token_address}: {e}")
            return None

    async def _call_contract_function(
        self,
        contract: Contract,
        function_name: str,
        *args
    ) -> Any:
        """Safely call a contract function."""
        try:
            func = getattr(contract.functions, function_name)
            result = await asyncio.to_thread(func(*args).call)
            return result
        except Exception:
            return None

    async def _verify_token(self, token_address: str) -> bool:
        """Verify if token is verified on block explorer."""
        # Would call block explorer API in production
        # For now, assume verified
        return True

    async def _check_audit_status(self, token_address: str) -> bool:
        """Check if token has been audited."""
        # Would check audit database in production
        return False

    async def _get_holder_count(self, token_address: str) -> Optional[int]:
        """Get number of token holders."""
        # Would fetch from block explorer API
        return 1000  # Placeholder

    async def _get_creation_info(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get token creation information."""
        # Would fetch from block explorer API
        return None

    # -----------------------------------------------------------------------
    # Token Supply Analysis
    # -----------------------------------------------------------------------

    async def analyze_supply(
        self,
        token_address: str,
        force_refresh: bool = False
    ) -> Optional[TokenSupply]:
        """Analyze token supply distribution."""
        token_address = Web3.to_checksum_address(token_address)

        if not force_refresh and token_address in self._token_supply_cache:
            return self._token_supply_cache[token_address]

        try:
            token_info = await self.get_token_info(token_address)
            if not token_info:
                return None

            # Get holders
            holders = await self.get_token_holders(token_address)
            if not holders:
                return None

            # Calculate distribution
            total_balance = sum(h.balance for h in holders)
            total_supply = token_info.total_supply

            # Categorize holders
            whale_balance = sum(h.balance for h in holders if h.balance / total_supply > 0.01)
            investor_balance = sum(h.balance for h in holders if 0.001 < h.balance / total_supply <= 0.01)
            retail_balance = sum(h.balance for h in holders if h.balance / total_supply <= 0.001)

            # Determine locked/staked/treasury amounts
            locked_supply = await self._get_locked_supply(token_address)
            staked_supply = await self._get_staked_supply(token_address)
            treasury_supply = await self._get_treasury_supply(token_address)

            # Calculate circulating supply
            circulating = total_supply - locked_supply - staked_supply - treasury_supply

            supply = TokenSupply(
                total_supply=total_supply,
                circulating_supply=max(0, circulating),
                max_supply=token_info.max_supply,
                locked_supply=locked_supply,
                staked_supply=staked_supply,
                treasury_supply=treasury_supply,
                team_supply=whale_balance,
                public_supply=retail_balance,
                distribution={
                    "whale": whale_balance / total_supply if total_supply > 0 else 0,
                    "investor": investor_balance / total_supply if total_supply > 0 else 0,
                    "retail": retail_balance / total_supply if total_supply > 0 else 0,
                },
            )

            self._token_supply_cache[token_address] = supply
            return supply

        except Exception as e:
            logger.error(f"Error analyzing supply for {token_address}: {e}")
            return None

    async def _get_locked_supply(self, token_address: str) -> float:
        """Get amount of locked tokens."""
        # Would fetch from lockup contracts
        return 0.0

    async def _get_staked_supply(self, token_address: str) -> float:
        """Get amount of staked tokens."""
        # Would fetch from staking contracts
        return 0.0

    async def _get_treasury_supply(self, token_address: str) -> float:
        """Get amount of tokens in treasury."""
        # Would fetch from treasury wallets
        return 0.0

    # -----------------------------------------------------------------------
    # Token Holders Analysis
    # -----------------------------------------------------------------------

    async def get_token_holders(
        self,
        token_address: str,
        limit: int = 100,
        force_refresh: bool = False
    ) -> List[TokenHolder]:
        """Get list of token holders."""
        token_address = Web3.to_checksum_address(token_address)

        if not force_refresh and token_address in self._token_holders_cache:
            return self._token_holders_cache[token_address]

        try:
            # Would fetch from block explorer API
            # For now, generate sample holders
            holders = await self._fetch_holders_from_blockchain(token_address, limit)

            self._token_holders_cache[token_address] = holders
            self._performance["holders_analyzed"] += len(holders)

            return holders

        except Exception as e:
            logger.error(f"Error getting holders for {token_address}: {e}")
            return []

    async def _fetch_holders_from_blockchain(
        self,
        token_address: str,
        limit: int
    ) -> List[TokenHolder]:
        """Fetch holders from blockchain."""
        # In production, would use block explorer API
        # This is a sample implementation
        holders = []
        total_supply = 1000000  # Placeholder

        for i in range(min(limit, 100)):
            holder = TokenHolder(
                address=f"0x{i:40x}",
                balance=total_supply * (1 - i / (limit + 1)) / limit,
                balance_usd=0.0,
                percentage=(1 - i / (limit + 1)) / limit * 100,
                rank=i + 1,
                is_contract=i % 10 == 0,
                is_exchange=i % 5 == 0,
                is_whale=i < 10,
                labels=["whale"] if i < 10 else [],
            )
            holders.append(holder)

        return holders

    async def analyze_holder_distribution(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """Analyze holder distribution."""
        holders = await self.get_token_holders(token_address)
        if not holders:
            return {}

        total_holders = len(holders)
        total_balance = sum(h.balance for h in holders)

        # Gini coefficient
        sorted_balances = sorted([h.balance for h in holders])
        n = len(sorted_balances)
        if n > 0:
            sum_abs_diff = 0
            for i in range(n):
                for j in range(n):
                    sum_abs_diff += abs(sorted_balances[i] - sorted_balances[j])
            gini = sum_abs_diff / (2 * n * sum(sorted_balances)) if sum(sorted_balances) > 0 else 0
        else:
            gini = 0

        # Concentration metrics
        top_10_balance = sum(h.balance for h in holders[:10])
        top_50_balance = sum(h.balance for h in holders[:50])
        top_100_balance = sum(h.balance for h in holders[:100])

        return {
            "total_holders": total_holders,
            "gini_coefficient": gini,
            "concentration": {
                "top_10": top_10_balance / total_balance if total_balance > 0 else 0,
                "top_50": top_50_balance / total_balance if total_balance > 0 else 0,
                "top_100": top_100_balance / total_balance if total_balance > 0 else 0,
            },
            "naka_satoshi_coefficient": self._calculate_naka_satoshi(holders),
            "distribution": self._calculate_distribution_percentiles(holders),
        }

    def _calculate_naka_satoshi(self, holders: List[TokenHolder]) -> float:
        """Calculate Naka Satoshi coefficient."""
        if not holders:
            return 0.0

        sorted_holders = sorted(holders, key=lambda h: h.balance, reverse=True)
        total = sum(h.balance for h in holders)

        cumulative = 0
        for i, holder in enumerate(sorted_holders):
            cumulative += holder.balance
            if cumulative / total > 0.51:
                return i + 1

        return len(holders)

    def _calculate_distribution_percentiles(
        self,
        holders: List[TokenHolder]
    ) -> Dict[str, float]:
        """Calculate distribution percentiles."""
        if not holders:
            return {}

        balances = sorted([h.balance for h in holders])

        return {
            "p10": np.percentile(balances, 10),
            "p25": np.percentile(balances, 25),
            "p50": np.percentile(balances, 50),
            "p75": np.percentile(balances, 75),
            "p90": np.percentile(balances, 90),
        }

    # -----------------------------------------------------------------------
    # Token Transactions
    # -----------------------------------------------------------------------

    async def get_token_transactions(
        self,
        token_address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[TokenTransaction]:
        """Get token transactions."""
        token_address = Web3.to_checksum_address(token_address)

        try:
            # In production, would fetch from block explorer API
            # This is a sample implementation
            transactions = await self._fetch_transactions(
                token_address,
                limit,
                from_block,
                to_block
            )

            self._performance["transactions_processed"] += len(transactions)
            self._token_transactions_cache[token_address].extend(transactions)

            return transactions

        except Exception as e:
            logger.error(f"Error getting transactions for {token_address}: {e}")
            return []

    async def _fetch_transactions(
        self,
        token_address: str,
        limit: int,
        from_block: Optional[int],
        to_block: Optional[int]
    ) -> List[TokenTransaction]:
        """Fetch transactions from blockchain."""
        # Sample implementation
        transactions = []
        now = datetime.utcnow()

        for i in range(min(limit, 100)):
            tx = TokenTransaction(
                hash=f"0x{i:64x}",
                from_address=f"0x{(i + 1):40x}",
                to_address=f"0x{(i + 2):40x}",
                amount=100 * (1 - i / (limit + 1)),
                amount_usd=100 * (1 - i / (limit + 1)) * 3500,
                price=3500,
                timestamp=now - timedelta(minutes=i * 5),
                block_number=10000000 + i,
                gas_price=50,
                gas_used=21000,
                transaction_type="transfer",
            )
            transactions.append(tx)

        return transactions

    async def analyze_transaction_patterns(
        self,
        token_address: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze transaction patterns."""
        transactions = self._token_transactions_cache.get(token_address, [])
        if not transactions:
            return {}

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [t for t in transactions if t.timestamp >= cutoff]

        if not recent:
            return {}

        # Basic stats
        total_volume = sum(t.amount_usd for t in recent)
        unique_senders = len(set(t.from_address for t in recent))
        unique_receivers = len(set(t.to_address for t in recent))

        # Hourly patterns
        hourly_volume = defaultdict(float)
        hourly_count = defaultdict(int)
        for tx in recent:
            hour = tx.timestamp.hour
            hourly_volume[hour] += tx.amount_usd
            hourly_count[hour] += 1

        # Largest transactions
        largest = sorted(recent, key=lambda t: t.amount_usd, reverse=True)[:10]

        return {
            "total_transactions": len(recent),
            "total_volume_usd": total_volume,
            "average_transaction_usd": total_volume / len(recent) if recent else 0,
            "unique_senders": unique_senders,
            "unique_receivers": unique_receivers,
            "hourly_patterns": {
                "volume": dict(hourly_volume),
                "count": dict(hourly_count),
            },
            "largest_transactions": [
                {
                    "hash": t.hash,
                    "from": t.from_address,
                    "to": t.to_address,
                    "amount_usd": t.amount_usd,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in largest
            ],
            "volatility": self._calculate_volume_volatility(recent),
        }

    def _calculate_volume_volatility(
        self,
        transactions: List[TokenTransaction]
    ) -> float:
        """Calculate volume volatility."""
        if len(transactions) < 2:
            return 0.0

        hourly_volumes = defaultdict(float)
        for tx in transactions:
            hourly_volumes[tx.timestamp.hour] += tx.amount_usd

        volumes = list(hourly_volumes.values())
        if len(volumes) < 2:
            return 0.0

        return np.std(volumes) / (np.mean(volumes) + 1e-10)

    # -----------------------------------------------------------------------
    # Token Risk Analysis
    # -----------------------------------------------------------------------

    async def analyze_token_risk(
        self,
        token_address: str
    ) -> Optional[TokenRiskAnalysis]:
        """Analyze token risk factors."""
        token_info = await self.get_token_info(token_address)
        if not token_info:
            return None

        holders = await self.get_token_holders(token_address)
        supply = await self.analyze_supply(token_address)

        risk_score = 0.0
        factors = []
        warnings = []
        recommendations = []

        # 1. Holder concentration risk
        if holders:
            distribution = await self.analyze_holder_distribution(token_address)
            concentration = distribution.get("concentration", {})
            top_10 = concentration.get("top_10", 0)

            if top_10 > 0.8:
                risk_score += 0.3
                factors.append({"factor": "holder_concentration", "value": top_10, "weight": 0.3})
                warnings.append("Very high holder concentration (>80% in top 10)")
                recommendations.append("Consider reducing exposure due to high holder concentration")
            elif top_10 > 0.6:
                risk_score += 0.2
                factors.append({"factor": "holder_concentration", "value": top_10, "weight": 0.2})
                warnings.append("High holder concentration (>60% in top 10)")

        # 2. Liquidity risk
        trading_info = await self.get_trading_info(token_address)
        if trading_info and trading_info.liquidity < 100000:
            risk_score += 0.2
            factors.append({"factor": "liquidity", "value": trading_info.liquidity, "weight": 0.2})
            warnings.append(f"Low liquidity: ${trading_info.liquidity:,.0f}")
            recommendations.append("Low liquidity may cause high slippage")

        # 3. Supply risk
        if supply:
            distribution = supply.distribution
            whale_share = distribution.get("whale", 0)

            if whale_share > 0.3:
                risk_score += 0.2
                factors.append({"factor": "whale_control", "value": whale_share, "weight": 0.2})
                warnings.append(f"High whale control: {whale_share:.1%} of supply")

            if supply.locked_supply > 0.5 * supply.total_supply:
                risk_score += 0.15
                factors.append({"factor": "locked_supply", "value": supply.locked_supply, "weight": 0.15})
                warnings.append(f"Large locked supply: {supply.locked_supply/supply.total_supply:.1%} of total")

        # 4. Age and verification risk
        if token_info.created_at:
            age_days = (datetime.utcnow() - token_info.created_at).days
            if age_days < 30:
                risk_score += 0.15
                factors.append({"factor": "token_age", "value": age_days, "weight": 0.15})
                warnings.append("Token is less than 30 days old")

        if not token_info.is_verified:
            risk_score += 0.15
            factors.append({"factor": "verification", "value": 0, "weight": 0.15})
            warnings.append("Token is not verified on block explorer")

        if not token_info.is_audited:
            risk_score += 0.1
            factors.append({"factor": "audit", "value": 0, "weight": 0.1})
            warnings.append("Token has not been audited")

        # 5. Volume risk
        if trading_info:
            if trading_info.volume_24h < 10000:
                risk_score += 0.1
                factors.append({"factor": "volume", "value": trading_info.volume_24h, "weight": 0.1})
                warnings.append("Very low 24h trading volume")

        # Determine risk level
        if risk_score >= 0.8:
            risk_level = TokenRiskLevel.CRITICAL
            recommendations.append("High risk token - avoid or very limited exposure")
        elif risk_score >= 0.6:
            risk_level = TokenRiskLevel.HIGH
            recommendations.append("High risk - proceed with caution and limit position size")
        elif risk_score >= 0.4:
            risk_level = TokenRiskLevel.MEDIUM
            recommendations.append("Moderate risk - maintain regular monitoring")
        elif risk_score >= 0.2:
            risk_level = TokenRiskLevel.LOW
            recommendations.append("Low risk - suitable for normal trading")
        else:
            risk_level = TokenRiskLevel.VERY_LOW
            recommendations.append("Very low risk - suitable for larger positions")

        # Check for scam indicators
        scam_indicators = await self._check_scam_indicators(token_address)
        if scam_indicators:
            risk_level = TokenRiskLevel.SCAM
            warnings.extend(scam_indicators)
            recommendations.append("⚠️ Potential scam detected - avoid this token")

        return TokenRiskAnalysis(
            risk_level=risk_level,
            risk_score=risk_score,
            factors=factors,
            warnings=warnings[:5],  # Limit to top 5
            recommendations=recommendations[:5],
            detailed_analysis={
                "holder_distribution": await self.analyze_holder_distribution(token_address) if holders else {},
                "transaction_patterns": await self.analyze_transaction_patterns(token_address) if holders else {},
            },
            confidence=1.0 - risk_score * 0.5,
        )

    async def _check_scam_indicators(
        self,
        token_address: str
    ) -> List[str]:
        """Check for scam indicators."""
        indicators = []

        token_info = await self.get_token_info(token_address)
        if not token_info:
            return indicators

        # Check for suspicious name patterns
        suspicious_patterns = [
            r'(?i)honey',
            r'(?i)ponzi',
            r'(?i)scam',
            r'(?i)rug',
            r'(?i)pump',
            r'(?i)dump',
        ]

        name = token_info.name.lower()
        symbol = token_info.symbol.lower()

        for pattern in suspicious_patterns:
            if re.search(pattern, name) or re.search(pattern, symbol):
                indicators.append(f"Suspicious name/symbol pattern: {pattern}")

        # Check holder distribution (very high concentration)
        holders = await self.get_token_holders(token_address, limit=10)
        if holders and len(holders) >= 3:
            top_balance = holders[0].balance
            second_balance = holders[1].balance if len(holders) > 1 else 0
            if top_balance > second_balance * 100:
                indicators.append("Extreme holder concentration (top holder has 100x more than second)")

        return indicators

    # -----------------------------------------------------------------------
    # Trading Information
    # -----------------------------------------------------------------------

    async def get_trading_info(
        self,
        token_address: str
    ) -> Optional[TokenTradingInfo]:
        """Get token trading information."""
        try:
            # In production, would fetch from DEX/CEX APIs
            # Sample implementation
            return TokenTradingInfo(
                price=3500,
                price_change_24h=5.2,
                price_change_7d=12.8,
                volume_24h=150000000,
                volume_change_24h=8.5,
                liquidity=50000000,
                market_cap=35000000000,
                fully_diluted_valuation=50000000000,
                circulating_supply=10000000,
                total_supply=15000000,
                holders=10000,
                exchanges=[
                    {"name": "Uniswap", "liquidity": 20000000, "volume": 80000000},
                    {"name": "Binance", "liquidity": 30000000, "volume": 70000000},
                ],
                pairs=[
                    {"pair": "ETH", "price": 0.001, "liquidity": 10000000},
                    {"pair": "USDC", "price": 1.0, "liquidity": 15000000},
                ],
                order_books={},
                volatility=0.25,
                spread=0.001,
                depth=1000000,
            )

        except Exception as e:
            logger.error(f"Error getting trading info for {token_address}: {e}")
            return None

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_token_contract(
        self,
        token_address: str
    ) -> Optional[Contract]:
        """Get token contract instance."""
        try:
            return self.web3_client.get_contract(
                token_address,
                abi=self._erc20_abi
            )
        except Exception:
            return None

    def format_amount(
        self,
        amount: float,
        decimals: int = 18
    ) -> str:
        """Format token amount with proper decimals."""
        return f"{amount / (10 ** decimals):.6f}"

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cached_tokens": len(self._token_cache),
            "cached_holders": sum(len(h) for h in self._token_holders_cache.values()),
            "cached_transactions": sum(len(t) for t in self._token_transactions_cache.values()),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the analyzer."""
        self._running = True
        logger.info("TokenAnalyzer started")

    async def stop(self) -> None:
        """Stop the analyzer."""
        self._running = False
        logger.info("TokenAnalyzer stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_token_analyzer(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> TokenAnalyzer:
    """Factory function to create a TokenAnalyzer instance."""
    return TokenAnalyzer(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the token analyzer
    pass

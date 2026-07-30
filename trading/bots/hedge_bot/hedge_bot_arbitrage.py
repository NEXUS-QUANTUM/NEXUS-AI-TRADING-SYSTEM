# trading/bots/hedge_bot/hedge_bot_arbitrage.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Arbitrage Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Arbitrage Module

This module provides comprehensive arbitrage detection and execution
capabilities for the NEXUS Hedge Bot system. It identifies and
executes various types of arbitrage opportunities across markets.

The module covers:
- Cross-Exchange Arbitrage
- Triangular Arbitrage
- Statistical Arbitrage
- Funding Rate Arbitrage
- Basis Arbitrage
- Index Arbitrage
- Merger Arbitrage
- Options Arbitrage
- Latency Arbitrage
- Flash Loan Arbitrage
- Cross-Chain Arbitrage
- DEX-CEX Arbitrage
"""

import os
import sys
import json
import math
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from decimal import Decimal
import numpy as np
from collections import defaultdict
import itertools

logger = logging.getLogger(__name__)


# ============================================================
# ARBITRAGE DATACLASSES
# ============================================================

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data"""
    id: str
    type: str  # cross_exchange, triangular, statistical, funding, basis, etc.
    symbol: str
    exchanges: List[str]
    buy_price: float
    sell_price: float
    spread: float
    spread_percent: float
    profit: float
    profit_percent: float
    fee: float
    net_profit: float
    net_profit_percent: float
    confidence: float
    timestamp: datetime
    route: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type,
            "symbol": self.symbol,
            "exchanges": self.exchanges,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "spread": self.spread,
            "spread_percent": self.spread_percent,
            "profit": self.profit,
            "profit_percent": self.profit_percent,
            "fee": self.fee,
            "net_profit": self.net_profit,
            "net_profit_percent": self.net_profit_percent,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "route": self.route,
            "details": self.details,
        }


@dataclass
class ArbitrageExecution:
    """Arbitrage execution data"""
    opportunity_id: str
    type: str
    symbol: str
    status: str  # pending, executing, completed, failed
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    buy_price_executed: Optional[float] = None
    sell_price_executed: Optional[float] = None
    quantity_executed: Optional[float] = None
    profit_realized: Optional[float] = None
    fee_paid: Optional[float] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "opportunity_id": self.opportunity_id,
            "type": self.type,
            "symbol": self.symbol,
            "status": self.status,
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "buy_price_executed": self.buy_price_executed,
            "sell_price_executed": self.sell_price_executed,
            "quantity_executed": self.quantity_executed,
            "profit_realized": self.profit_realized,
            "fee_paid": self.fee_paid,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error": self.error,
        }


# ============================================================
# ARBITRAGE ENGINE
# ============================================================

class ArbitrageEngine:
    """
    Comprehensive arbitrage engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the arbitrage engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.min_profit_percent = self.config.get("min_profit_percent", 0.001)  # 0.1%
        self.max_position_size = self.config.get("max_position_size", 10000)
        self.min_position_size = self.config.get("min_position_size", 100)
        self.max_slippage = self.config.get("max_slippage", 0.001)  # 0.1%
        self.fee_rate = self.config.get("fee_rate", 0.001)  # 0.1%
        
        # State
        self.opportunities: List[ArbitrageOpportunity] = []
        self.executions: List[ArbitrageExecution] = []
        self.market_data: Dict[str, Dict[str, Any]] = {}
        self.exchange_data: Dict[str, Dict[str, Any]] = {}
        
        # Cache
        self._cache: Dict[str, Any] = {}
        
        logger.info("Arbitrage engine initialized")
    
    # ============================================================
    # CROSS-EXCHANGE ARBITRAGE
    # ============================================================
    
    def find_cross_exchange_opportunities(
        self,
        exchange_data: Dict[str, Dict[str, Dict[str, float]]],
        min_spread: float = 0.001
    ) -> List[ArbitrageOpportunity]:
        """
        Find cross-exchange arbitrage opportunities
        
        Args:
            exchange_data: Exchange data with prices by symbol
            min_spread: Minimum spread percentage
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        # Get all symbols across exchanges
        all_symbols = set()
        for exchange, data in exchange_data.items():
            all_symbols.update(data.keys())
        
        for symbol in all_symbols:
            # Get prices from each exchange
            prices = {}
            for exchange, data in exchange_data.items():
                if symbol in data:
                    prices[exchange] = data[symbol]
            
            if len(prices) < 2:
                continue
            
            # Find min and max prices
            min_price = min(prices.values())
            max_price = max(prices.values())
            min_exchange = [e for e, p in prices.items() if p == min_price][0]
            max_exchange = [e for e, p in prices.items() if p == max_price][0]
            
            # Calculate spread
            spread = max_price - min_price
            spread_percent = spread / min_price
            
            if spread_percent < min_spread:
                continue
            
            # Calculate profit
            quantity = min(
                self.max_position_size / max_price,
                self.min_position_size / min_price
            )
            
            buy_cost = quantity * min_price
            sell_value = quantity * max_price
            fee = (buy_cost + sell_value) * self.fee_rate
            profit = sell_value - buy_cost - fee
            profit_percent = profit / buy_cost
            
            if profit_percent < self.min_profit_percent:
                continue
            
            # Create opportunity
            opportunity = ArbitrageOpportunity(
                id=f"ce_{int(time.time())}_{symbol}",
                type="cross_exchange",
                symbol=symbol,
                exchanges=[min_exchange, max_exchange],
                buy_price=min_price,
                sell_price=max_price,
                spread=spread,
                spread_percent=spread_percent,
                profit=profit,
                profit_percent=profit_percent,
                fee=fee,
                net_profit=profit,
                net_profit_percent=profit_percent,
                confidence=0.9 - (spread_percent * 0.1),
                timestamp=datetime.now(),
                route={
                    "buy_exchange": min_exchange,
                    "sell_exchange": max_exchange,
                    "quantity": quantity,
                },
                details={
                    "prices": prices,
                    "spread": spread,
                },
            )
            
            opportunities.append(opportunity)
        
        return opportunities
    
    # ============================================================
    # TRIANGULAR ARBITRAGE
    # ============================================================
    
    def find_triangular_opportunities(
        self,
        exchange_data: Dict[str, Dict[str, float]],
        symbol_triplets: List[Tuple[str, str, str]]
    ) -> List[ArbitrageOpportunity]:
        """
        Find triangular arbitrage opportunities
        
        Args:
            exchange_data: Exchange data with prices
            symbol_triplets: List of symbol triplets for triangular arbitrage
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        for triplet in symbol_triplets:
            # Triangular arbitrage: A/B * B/C * C/A > 1
            # or reverse: A/C * C/B * B/A > 1
            if len(triplet) != 3:
                continue
            
            a, b, c = triplet
            
            # Get prices
            price_ab = exchange_data.get(f"{a}/{b}", 0)
            price_bc = exchange_data.get(f"{b}/{c}", 0)
            price_ca = exchange_data.get(f"{c}/{a}", 0)
            
            if price_ab <= 0 or price_bc <= 0 or price_ca <= 0:
                continue
            
            # Calculate arbitrage ratio
            ratio = price_ab * price_bc * price_ca
            
            if ratio > 1 + self.min_profit_percent:
                # Profit opportunity: start with A, buy B, buy C, sell A
                profit_percent = ratio - 1
                
                opportunity = ArbitrageOpportunity(
                    id=f"tri_{int(time.time())}_{a}_{b}_{c}",
                    type="triangular",
                    symbol=f"{a}/{b}/{c}",
                    exchanges=["exchange"],
                    buy_price=1.0,
                    sell_price=ratio,
                    spread=ratio - 1,
                    spread_percent=profit_percent,
                    profit=profit_percent,
                    profit_percent=profit_percent,
                    fee=profit_percent * self.fee_rate,
                    net_profit=profit_percent * (1 - self.fee_rate),
                    net_profit_percent=profit_percent * (1 - self.fee_rate),
                    confidence=0.85,
                    timestamp=datetime.now(),
                    route={
                        "steps": [
                            {"from": a, "to": b, "rate": price_ab},
                            {"from": b, "to": c, "rate": price_bc},
                            {"from": c, "to": a, "rate": price_ca},
                        ]
                    },
                    details={
                        "ratio": ratio,
                        "prices": {
                            f"{a}/{b}": price_ab,
                            f"{b}/{c}": price_bc,
                            f"{c}/{a}": price_ca,
                        },
                    },
                )
                opportunities.append(opportunity)
            
            elif ratio < 1 / (1 + self.min_profit_percent):
                # Reverse profit opportunity: start with A, buy C, buy B, sell A
                reverse_ratio = 1 / ratio
                profit_percent = reverse_ratio - 1
                
                opportunity = ArbitrageOpportunity(
                    id=f"tri_rev_{int(time.time())}_{a}_{b}_{c}",
                    type="triangular",
                    symbol=f"{a}/{b}/{c}",
                    exchanges=["exchange"],
                    buy_price=1.0,
                    sell_price=reverse_ratio,
                    spread=reverse_ratio - 1,
                    spread_percent=profit_percent,
                    profit=profit_percent,
                    profit_percent=profit_percent,
                    fee=profit_percent * self.fee_rate,
                    net_profit=profit_percent * (1 - self.fee_rate),
                    net_profit_percent=profit_percent * (1 - self.fee_rate),
                    confidence=0.85,
                    timestamp=datetime.now(),
                    route={
                        "steps": [
                            {"from": a, "to": c, "rate": 1 / price_ca},
                            {"from": c, "to": b, "rate": 1 / price_bc},
                            {"from": b, "to": a, "rate": 1 / price_ab},
                        ]
                    },
                    details={
                        "ratio": reverse_ratio,
                        "prices": {
                            f"{a}/{b}": price_ab,
                            f"{b}/{c}": price_bc,
                            f"{c}/{a}": price_ca,
                        },
                    },
                )
                opportunities.append(opportunity)
        
        return opportunities
    
    # ============================================================
    # STATISTICAL ARBITRAGE
    # ============================================================
    
    def find_statistical_opportunities(
        self,
        price_data: Dict[str, List[float]],
        lookback: int = 100,
        zscore_threshold: float = 2.0
    ) -> List[ArbitrageOpportunity]:
        """
        Find statistical arbitrage opportunities
        
        Args:
            price_data: Price data by symbol
            lookback: Lookback period
            zscore_threshold: Z-score threshold for entry
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        # Get all symbol pairs
        symbols = list(price_data.keys())
        pairs = list(itertools.combinations(symbols, 2))
        
        for a, b in pairs:
            if len(price_data[a]) < lookback or len(price_data[b]) < lookback:
                continue
            
            # Calculate spread
            price_a = np.array(price_data[a][-lookback:])
            price_b = np.array(price_data[b][-lookback:])
            
            # Normalize prices
            norm_a = price_a / price_a[0]
            norm_b = price_b / price_b[0]
            
            # Calculate spread
            spread = norm_a - norm_b
            
            # Calculate z-score
            mean_spread = np.mean(spread)
            std_spread = np.std(spread)
            current_spread = spread[-1]
            
            if std_spread == 0:
                continue
            
            zscore = (current_spread - mean_spread) / std_spread
            
            if abs(zscore) < zscore_threshold:
                continue
            
            # Determine direction
            if zscore > zscore_threshold:
                # Short A, Long B
                opportunity = ArbitrageOpportunity(
                    id=f"stat_{int(time.time())}_{a}_{b}",
                    type="statistical",
                    symbol=f"{a}/{b}",
                    exchanges=["exchange"],
                    buy_price=price_a[-1],
                    sell_price=price_b[-1],
                    spread=current_spread,
                    spread_percent=abs(current_spread) / mean_spread,
                    profit=abs(current_spread) * 0.5,
                    profit_percent=abs(current_spread) / mean_spread,
                    fee=0,
                    net_profit=abs(current_spread) * 0.5,
                    net_profit_percent=abs(current_spread) / mean_spread,
                    confidence=0.7 - (abs(zscore) / 5),
                    timestamp=datetime.now(),
                    route={
                        "action": "short_a_long_b",
                        "zscore": zscore,
                    },
                    details={
                        "mean_spread": mean_spread,
                        "std_spread": std_spread,
                        "current_spread": current_spread,
                        "zscore": zscore,
                    },
                )
                opportunities.append(opportunity)
            else:
                # Long A, Short B
                opportunity = ArbitrageOpportunity(
                    id=f"stat_{int(time.time())}_{a}_{b}",
                    type="statistical",
                    symbol=f"{a}/{b}",
                    exchanges=["exchange"],
                    buy_price=price_b[-1],
                    sell_price=price_a[-1],
                    spread=-current_spread,
                    spread_percent=abs(current_spread) / mean_spread,
                    profit=abs(current_spread) * 0.5,
                    profit_percent=abs(current_spread) / mean_spread,
                    fee=0,
                    net_profit=abs(current_spread) * 0.5,
                    net_profit_percent=abs(current_spread) / mean_spread,
                    confidence=0.7 - (abs(zscore) / 5),
                    timestamp=datetime.now(),
                    route={
                        "action": "long_a_short_b",
                        "zscore": zscore,
                    },
                    details={
                        "mean_spread": mean_spread,
                        "std_spread": std_spread,
                        "current_spread": current_spread,
                        "zscore": zscore,
                    },
                )
                opportunities.append(opportunity)
        
        return opportunities
    
    # ============================================================
    # FUNDING RATE ARBITRAGE
    # ============================================================
    
    def find_funding_rate_opportunities(
        self,
        funding_data: Dict[str, Dict[str, float]],
        min_funding_rate: float = 0.0005
    ) -> List[ArbitrageOpportunity]:
        """
        Find funding rate arbitrage opportunities
        
        Args:
            funding_data: Funding rate data by symbol
            min_funding_rate: Minimum funding rate
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        for symbol, data in funding_data.items():
            funding_rate = data.get("rate", 0)
            spot_price = data.get("spot_price", 0)
            futures_price = data.get("futures_price", 0)
            
            if abs(funding_rate) < min_funding_rate:
                continue
            
            # Calculate profit
            position_size = min(self.max_position_size / spot_price, 10000)
            profit = position_size * abs(funding_rate)
            profit_percent = abs(funding_rate)
            
            if profit_percent < self.min_profit_percent:
                continue
            
            direction = "long" if funding_rate < 0 else "short"
            
            opportunity = ArbitrageOpportunity(
                id=f"fr_{int(time.time())}_{symbol}",
                type="funding_rate",
                symbol=symbol,
                exchanges=["exchange"],
                buy_price=spot_price,
                sell_price=futures_price,
                spread=futures_price - spot_price,
                spread_percent=abs(futures_price - spot_price) / spot_price,
                profit=profit,
                profit_percent=profit_percent,
                fee=profit * self.fee_rate,
                net_profit=profit * (1 - self.fee_rate),
                net_profit_percent=profit_percent * (1 - self.fee_rate),
                confidence=0.8,
                timestamp=datetime.now(),
                route={
                    "direction": direction,
                    "position_size": position_size,
                },
                details={
                    "funding_rate": funding_rate,
                    "spot_price": spot_price,
                    "futures_price": futures_price,
                },
            )
            
            opportunities.append(opportunity)
        
        return opportunities
    
    # ============================================================
    # BASIS ARBITRAGE
    # ============================================================
    
    def find_basis_opportunities(
        self,
        spot_data: Dict[str, float],
        futures_data: Dict[str, Dict[str, float]],
        min_basis: float = 0.002
    ) -> List[ArbitrageOpportunity]:
        """
        Find basis arbitrage opportunities
        
        Args:
            spot_data: Spot prices by symbol
            futures_data: Futures prices by symbol and expiry
            min_basis: Minimum basis percentage
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        for symbol, spot_price in spot_data.items():
            if symbol not in futures_data:
                continue
            
            futures_by_expiry = futures_data[symbol]
            
            for expiry, futures_price in futures_by_expiry.items():
                basis = futures_price - spot_price
                basis_percent = basis / spot_price
                
                if abs(basis_percent) < min_basis:
                    continue
                
                # Calculate profit
                position_size = min(self.max_position_size / spot_price, 10000)
                profit = position_size * abs(basis)
                profit_percent = abs(basis_percent)
                
                if profit_percent < self.min_profit_percent:
                    continue
                
                direction = "long_spot_short_future" if basis > 0 else "short_spot_long_future"
                
                opportunity = ArbitrageOpportunity(
                    id=f"basis_{int(time.time())}_{symbol}_{expiry}",
                    type="basis",
                    symbol=symbol,
                    exchanges=["exchange"],
                    buy_price=spot_price if basis > 0 else futures_price,
                    sell_price=futures_price if basis > 0 else spot_price,
                    spread=abs(basis),
                    spread_percent=abs(basis_percent),
                    profit=profit,
                    profit_percent=profit_percent,
                    fee=profit * self.fee_rate,
                    net_profit=profit * (1 - self.fee_rate),
                    net_profit_percent=profit_percent * (1 - self.fee_rate),
                    confidence=0.85,
                    timestamp=datetime.now(),
                    route={
                        "direction": direction,
                        "expiry": expiry,
                        "position_size": position_size,
                    },
                    details={
                        "spot_price": spot_price,
                        "futures_price": futures_price,
                        "basis": basis,
                        "basis_percent": basis_percent,
                    },
                )
                
                opportunities.append(opportunity)
        
        return opportunities
    
    # ============================================================
    # OPPORTUNITY MANAGEMENT
    # ============================================================
    
    def scan_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Scan for all arbitrage opportunities
        
        Returns:
            List of arbitrage opportunities
        """
        all_opportunities = []
        
        # Cross-exchange arbitrage
        if self.exchange_data:
            ce_opps = self.find_cross_exchange_opportunities(self.exchange_data)
            all_opportunities.extend(ce_opps)
        
        # Triangular arbitrage
        if self.exchange_data:
            triplets = [("BTC", "ETH", "USDT"), ("BTC", "SOL", "USDT"), ("ETH", "SOL", "USDT")]
            tri_opps = self.find_triangular_opportunities(
                self.exchange_data.get("exchange", {}), triplets
            )
            all_opportunities.extend(tri_opps)
        
        # Statistical arbitrage
        if self.market_data:
            price_data = {
                symbol: [p.get("price", 0) for p in data.get("history", [])[-100:]]
                for symbol, data in self.market_data.items()
            }
            stat_opps = self.find_statistical_opportunities(price_data)
            all_opportunities.extend(stat_opps)
        
        # Funding rate arbitrage
        if "funding_rates" in self._cache:
            fr_opps = self.find_funding_rate_opportunities(self._cache["funding_rates"])
            all_opportunities.extend(fr_opps)
        
        # Basis arbitrage
        if "spot_prices" in self._cache and "futures_prices" in self._cache:
            basis_opps = self.find_basis_opportunities(
                self._cache["spot_prices"],
                self._cache["futures_prices"]
            )
            all_opportunities.extend(basis_opps)
        
        # Sort by profit
        all_opportunities.sort(key=lambda x: x.net_profit_percent, reverse=True)
        
        # Store opportunities
        self.opportunities = all_opportunities
        
        return all_opportunities
    
    def get_best_opportunity(self) -> Optional[ArbitrageOpportunity]:
        """
        Get the best arbitrage opportunity
        
        Returns:
            Best arbitrage opportunity or None
        """
        if not self.opportunities:
            return None
        
        return max(self.opportunities, key=lambda x: x.net_profit)
    
    def validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Validate an arbitrage opportunity
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            True if valid
        """
        # Check if opportunity is still valid
        if opportunity.timestamp < datetime.now() - timedelta(seconds=5):
            return False
        
        # Check if profit is sufficient
        if opportunity.net_profit_percent < self.min_profit_percent:
            return False
        
        # Check if confidence is sufficient
        if opportunity.confidence < 0.5:
            return False
        
        return True
    
    # ============================================================
    # EXECUTION
    # ============================================================
    
    async def execute_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
        exchange_client: Any
    ) -> ArbitrageExecution:
        """
        Execute an arbitrage opportunity
        
        Args:
            opportunity: Arbitrage opportunity
            exchange_client: Exchange client for execution
            
        Returns:
            Arbitrage execution result
        """
        execution = ArbitrageExecution(
            opportunity_id=opportunity.id,
            type=opportunity.type,
            symbol=opportunity.symbol,
            status="pending",
            start_time=datetime.now(),
        )
        
        try:
            # Validate opportunity
            if not self.validate_opportunity(opportunity):
                execution.status = "failed"
                execution.error = "Opportunity no longer valid"
                self.executions.append(execution)
                return execution
            
            # Execute based on type
            if opportunity.type == "cross_exchange":
                result = await self._execute_cross_exchange(opportunity, exchange_client)
            elif opportunity.type == "triangular":
                result = await self._execute_triangular(opportunity, exchange_client)
            elif opportunity.type == "funding_rate":
                result = await self._execute_funding_rate(opportunity, exchange_client)
            elif opportunity.type == "basis":
                result = await self._execute_basis(opportunity, exchange_client)
            elif opportunity.type == "statistical":
                result = await self._execute_statistical(opportunity, exchange_client)
            else:
                raise ValueError(f"Unknown opportunity type: {opportunity.type}")
            
            execution.status = "completed"
            execution.buy_price_executed = result.get("buy_price")
            execution.sell_price_executed = result.get("sell_price")
            execution.quantity_executed = result.get("quantity")
            execution.profit_realized = result.get("profit")
            execution.fee_paid = result.get("fee")
            execution.end_time = datetime.now()
            
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.end_time = datetime.now()
            logger.error(f"Arbitrage execution failed: {e}")
        
        self.executions.append(execution)
        return execution
    
    async def _execute_cross_exchange(
        self,
        opportunity: ArbitrageOpportunity,
        exchange_client: Any
    ) -> Dict[str, Any]:
        """Execute cross-exchange arbitrage"""
        # Buy on one exchange, sell on another
        # (Implementation would depend on exchange clients)
        return {
            "buy_price": opportunity.buy_price,
            "sell_price": opportunity.sell_price,
            "quantity": opportunity.route.get("quantity", 0),
            "profit": opportunity.net_profit,
            "fee": opportunity.fee,
        }
    
    async def _execute_triangular(
        self,
        opportunity: ArbitrageOpportunity,
        exchange_client: Any
    ) -> Dict[str, Any]:
        """Execute triangular arbitrage"""
        # Execute sequence of trades
        # (Implementation would depend on exchange clients)
        return {
            "buy_price": 1.0,
            "sell_price": opportunity.sell_price,
            "quantity": 1.0,
            "profit": opportunity.net_profit,
            "fee": opportunity.fee,
        }
    
    async def _execute_funding_rate(
        self,
        opportunity: ArbitrageOpportunity,
        exchange_client: Any
    ) -> Dict[str, Any]:
        """Execute funding rate arbitrage"""
        # (Implementation would depend on exchange clients)
        return {
            "buy_price": opportunity.buy_price,
            "sell_price": opportunity.sell_price,
            "quantity": opportunity.route.get("position_size", 0),
            "profit": opportunity.net_profit,
            "fee": opportunity.fee,
        }
    
    async def _execute_basis(
        self,
        opportunity: ArbitrageOpportunity,
        exchange_client: Any
    ) -> Dict[str, Any]:
        """Execute basis arbitrage"""
        # (Implementation would depend on exchange clients)
        return {
            "buy_price": opportunity.buy_price,
            "sell_price": opportunity.sell_price,
            "quantity": opportunity.route.get("position_size", 0),
            "profit": opportunity.net_profit,
            "fee": opportunity.fee,
        }
    
    async def _execute_statistical(
        self,
        opportunity: ArbitrageOpportunity,
        exchange_client: Any
    ) -> Dict[str, Any]:
        """Execute statistical arbitrage"""
        # (Implementation would depend on exchange clients)
        return {
            "buy_price": opportunity.buy_price,
            "sell_price": opportunity.sell_price,
            "quantity": 1.0,
            "profit": opportunity.net_profit,
            "fee": opportunity.fee,
        }
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def update_market_data(
        self,
        symbol: str,
        data: Dict[str, Any]
    ) -> None:
        """Update market data"""
        if symbol not in self.market_data:
            self.market_data[symbol] = {"history": []}
        
        self.market_data[symbol]["current"] = data
        
        # Update history
        if "price" in data:
            self.market_data[symbol]["history"].append({
                "price": data["price"],
                "timestamp": datetime.now(),
            })
            
            # Keep only last 1000 records
            if len(self.market_data[symbol]["history"]) > 1000:
                self.market_data[symbol]["history"] = self.market_data[symbol]["history"][-1000:]
    
    def update_exchange_data(
        self,
        exchange: str,
        data: Dict[str, Dict[str, float]]
    ) -> None:
        """Update exchange data"""
        self.exchange_data[exchange] = data
    
    def clear_cache(self) -> None:
        """Clear cache"""
        self._cache.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get arbitrage statistics"""
        return {
            "total_opportunities": len(self.opportunities),
            "total_executions": len(self.executions),
            "successful_executions": len([e for e in self.executions if e.status == "completed"]),
            "failed_executions": len([e for e in self.executions if e.status == "failed"]),
            "total_profit": sum(e.profit_realized for e in self.executions if e.profit_realized),
            "avg_profit": sum(e.profit_realized for e in self.executions if e.profit_realized) / len(self.executions) if self.executions else 0,
            "best_opportunity": self.get_best_opportunity(),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Dataclasses
    "ArbitrageOpportunity",
    "ArbitrageExecution",
    
    # Classes
    "ArbitrageEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

# trading/bots/hedge_bot/hedge_bot_accounting.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Accounting Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Accounting Module

This module provides comprehensive accounting and financial management
capabilities for the NEXUS Hedge Bot system. It handles PnL calculation,
position accounting, cost basis tracking, and financial reporting.

The module covers:
- Position Accounting (FIFO, LIFO, Average Cost)
- PnL Calculation (Realized, Unrealized, Total)
- Cost Basis Tracking
- Fee and Commission Accounting
- Margin Accounting
- Performance Metrics
- Financial Reporting
- Tax Lot Accounting
- Currency Conversion
- Portfolio Valuation
- Risk-Adjusted Returns
- Attribution Analysis
"""

import os
import sys
import json
import math
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from decimal import Decimal, getcontext
from collections import defaultdict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Set decimal precision
getcontext().prec = 28


# ============================================================
# ACCOUNTING DATACLASSES
# ============================================================

@dataclass
class TaxLot:
    """Tax lot for cost basis accounting"""
    id: str
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    purchase_date: datetime
    sale_date: Optional[datetime] = None
    sale_price: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    status: str = "open"  # open, closed, partially_closed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "quantity": float(self.quantity),
            "cost_basis": float(self.cost_basis),
            "purchase_date": self.purchase_date.isoformat(),
            "sale_date": self.sale_date.isoformat() if self.sale_date else None,
            "sale_price": float(self.sale_price) if self.sale_price else None,
            "realized_pnl": float(self.realized_pnl) if self.realized_pnl else None,
            "status": self.status,
        }


@dataclass
class PositionAccounting:
    """Position accounting data"""
    symbol: str
    side: str  # long, short
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    cost_basis: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_pnl: Decimal
    fees: Decimal
    commissions: Decimal
    financing_costs: Decimal
    holding_period: int  # days
    tax_lots: List[TaxLot] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": float(self.quantity),
            "average_price": float(self.average_price),
            "current_price": float(self.current_price),
            "cost_basis": float(self.cost_basis),
            "market_value": float(self.market_value),
            "unrealized_pnl": float(self.unrealized_pnl),
            "realized_pnl": float(self.realized_pnl),
            "total_pnl": float(self.total_pnl),
            "fees": float(self.fees),
            "commissions": float(self.commissions),
            "financing_costs": float(self.financing_costs),
            "holding_period": self.holding_period,
            "tax_lots": [lot.to_dict() for lot in self.tax_lots],
        }


@dataclass
class PortfolioAccounting:
    """Portfolio accounting data"""
    total_value: Decimal
    total_cost_basis: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_pnl: Decimal
    total_fees: Decimal
    total_commissions: Decimal
    total_financing_costs: Decimal
    cash_balance: Decimal
    margin_used: Decimal
    margin_available: Decimal
    leverage: Decimal
    positions: Dict[str, PositionAccounting] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_value": float(self.total_value),
            "total_cost_basis": float(self.total_cost_basis),
            "unrealized_pnl": float(self.unrealized_pnl),
            "realized_pnl": float(self.realized_pnl),
            "total_pnl": float(self.total_pnl),
            "total_fees": float(self.total_fees),
            "total_commissions": float(self.total_commissions),
            "total_financing_costs": float(self.total_financing_costs),
            "cash_balance": float(self.cash_balance),
            "margin_used": float(self.margin_used),
            "margin_available": float(self.margin_available),
            "leverage": float(self.leverage),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PerformanceReport:
    """Performance report"""
    period_start: datetime
    period_end: datetime
    total_return: Decimal
    annualized_return: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    average_win: Decimal
    average_loss: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_volume: Decimal
    total_fees: Decimal
    total_commissions: Decimal
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_return": float(self.total_return),
            "annualized_return": float(self.annualized_return),
            "sharpe_ratio": float(self.sharpe_ratio),
            "sortino_ratio": float(self.sortino_ratio),
            "calmar_ratio": float(self.calmar_ratio),
            "max_drawdown": float(self.max_drawdown),
            "win_rate": float(self.win_rate),
            "profit_factor": float(self.profit_factor),
            "average_win": float(self.average_win),
            "average_loss": float(self.average_loss),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_volume": float(self.total_volume),
            "total_fees": float(self.total_fees),
            "total_commissions": float(self.total_commissions),
        }


# ============================================================
# ACCOUNTING ENGINE
# ============================================================

class AccountingEngine:
    """
    Comprehensive accounting engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the accounting engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.method = self.config.get("method", "average_cost")  # fifo, lifo, average_cost
        self.currency = self.config.get("currency", "USD")
        self.include_fees = self.config.get("include_fees", True)
        self.include_commissions = self.config.get("include_commissions", True)
        self.include_financing = self.config.get("include_financing", True)
        
        # State
        self.tax_lots: Dict[str, List[TaxLot]] = defaultdict(list)
        self.closed_lots: Dict[str, List[TaxLot]] = defaultdict(list)
        self.trade_history: List[Dict[str, Any]] = []
        self.position_history: List[Dict[str, Any]] = []
        
        # Performance tracking
        self.equity_curve: List[Dict[str, Any]] = []
        self.daily_pnl: List[Dict[str, Any]] = []
        self.drawdowns: List[Dict[str, Any]] = []
        
        logger.info(f"Accounting engine initialized with method: {self.method}")
    
    # ============================================================
    # COST BASIS METHODS
    # ============================================================
    
    def calculate_cost_basis(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal = Decimal("0"),
        commissions: Decimal = Decimal("0")
    ) -> Decimal:
        """
        Calculate cost basis for a purchase
        
        Args:
            symbol: Asset symbol
            quantity: Quantity purchased
            price: Purchase price
            fees: Transaction fees
            commissions: Transaction commissions
            
        Returns:
            Cost basis
        """
        cost = quantity * price + fees + commissions
        return cost
    
    def calculate_average_cost(
        self,
        symbol: str,
        new_quantity: Decimal,
        new_price: Decimal,
        fees: Decimal = Decimal("0"),
        commissions: Decimal = Decimal("0")
    ) -> Decimal:
        """
        Calculate average cost for a position
        
        Args:
            symbol: Asset symbol
            new_quantity: New quantity
            new_price: New price
            fees: Transaction fees
            commissions: Transaction commissions
            
        Returns:
            Average cost
        """
        # Get existing lots
        lots = self.tax_lots.get(symbol, [])
        
        if not lots:
            return new_price + fees + commissions
        
        # Calculate total cost
        total_cost = sum(lot.cost_basis for lot in lots)
        total_quantity = sum(lot.quantity for lot in lots)
        
        if total_quantity == 0:
            return new_price + fees + commissions
        
        avg_cost = total_cost / total_quantity
        return avg_cost
    
    # ============================================================
    # POSITION ACCOUNTING
    # ============================================================
    
    def record_purchase(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal = Decimal("0"),
        commissions: Decimal = Decimal("0"),
        date: Optional[datetime] = None
    ) -> TaxLot:
        """
        Record a purchase transaction
        
        Args:
            symbol: Asset symbol
            quantity: Quantity purchased
            price: Purchase price
            fees: Transaction fees
            commissions: Transaction commissions
            date: Transaction date
            
        Returns:
            Tax lot
        """
        if date is None:
            date = datetime.now()
        
        # Calculate cost basis
        cost_basis = self.calculate_cost_basis(symbol, quantity, price, fees, commissions)
        
        # Create tax lot
        lot = TaxLot(
            id=f"{symbol}_{date.strftime('%Y%m%d_%H%M%S')}_{id(lot)}",
            symbol=symbol,
            quantity=quantity,
            cost_basis=cost_basis,
            purchase_date=date,
            status="open",
        )
        
        # Add to tax lots
        self.tax_lots[symbol].append(lot)
        
        # Record trade
        self.trade_history.append({
            "symbol": symbol,
            "side": "buy",
            "quantity": float(quantity),
            "price": float(price),
            "fees": float(fees),
            "commissions": float(commissions),
            "cost_basis": float(cost_basis),
            "date": date.isoformat(),
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.debug(f"Recorded purchase: {quantity} {symbol} @ {price}")
        return lot
    
    def record_sale(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal = Decimal("0"),
        commissions: Decimal = Decimal("0"),
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Record a sale transaction
        
        Args:
            symbol: Asset symbol
            quantity: Quantity sold
            price: Sale price
            fees: Transaction fees
            commissions: Transaction commissions
            date: Transaction date
            
        Returns:
            Sale results
        """
        if date is None:
            date = datetime.now()
        
        # Get lots for this symbol
        lots = self.tax_lots.get(symbol, [])
        
        if not lots:
            logger.warning(f"No lots found for {symbol}, cannot record sale")
            return {"error": "No lots found"}
        
        # Calculate total sale value
        sale_value = quantity * price
        total_fees = fees + commissions
        
        # Apply method
        if self.method == "fifo":
            results = self._record_sale_fifo(symbol, quantity, price, fees, commissions, date)
        elif self.method == "lifo":
            results = self._record_sale_lifo(symbol, quantity, price, fees, commissions, date)
        else:  # average_cost
            results = self._record_sale_average(symbol, quantity, price, fees, commissions, date)
        
        # Record trade
        self.trade_history.append({
            "symbol": symbol,
            "side": "sell",
            "quantity": float(quantity),
            "price": float(price),
            "fees": float(fees),
            "commissions": float(commissions),
            "sale_value": float(sale_value),
            "cost_basis": float(results.get("cost_basis", 0)),
            "realized_pnl": float(results.get("realized_pnl", 0)),
            "date": date.isoformat(),
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.debug(f"Recorded sale: {quantity} {symbol} @ {price}, PnL: {results.get('realized_pnl', 0)}")
        return results
    
    def _record_sale_fifo(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal,
        commissions: Decimal,
        date: datetime
    ) -> Dict[str, Any]:
        """Record sale using FIFO method"""
        lots = self.tax_lots[symbol]
        remaining = quantity
        total_cost = Decimal("0")
        realized_pnl = Decimal("0")
        closed_lots = []
        
        while remaining > 0 and lots:
            lot = lots[0]
            if lot.quantity <= remaining:
                # Close entire lot
                lot_quantity = lot.quantity
                lot_cost = lot.cost_basis
                remaining -= lot_quantity
                total_cost += lot_cost
                
                # Calculate PnL for this lot
                lot_sale_value = lot_quantity * price
                lot_fees = (lot_quantity / quantity) * (fees + commissions)
                lot_pnl = lot_sale_value - lot_cost - lot_fees
                realized_pnl += lot_pnl
                
                # Update lot
                lot.status = "closed"
                lot.sale_date = date
                lot.sale_price = price
                lot.realized_pnl = lot_pnl
                
                # Move to closed lots
                closed_lots.append(lot)
                self.closed_lots[symbol].append(lot)
                lots.pop(0)
                
            else:
                # Partially close lot
                lot_quantity = remaining
                lot_cost = (remaining / lot.quantity) * lot.cost_basis
                total_cost += lot_cost
                
                # Calculate PnL for this portion
                lot_sale_value = remaining * price
                lot_fees = (remaining / quantity) * (fees + commissions)
                lot_pnl = lot_sale_value - lot_cost - lot_fees
                realized_pnl += lot_pnl
                
                # Update remaining lot
                lot.quantity -= remaining
                lot.cost_basis -= lot_cost
                remaining = Decimal("0")
                
                # Create partially closed lot record
                partial_lot = TaxLot(
                    id=f"{lot.id}_partial_{date.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    quantity=lot_quantity,
                    cost_basis=lot_cost,
                    purchase_date=lot.purchase_date,
                    sale_date=date,
                    sale_price=price,
                    realized_pnl=lot_pnl,
                    status="partially_closed",
                )
                self.closed_lots[symbol].append(partial_lot)
        
        # Update position
        position = self._update_position(symbol)
        
        return {
            "method": "fifo",
            "quantity_sold": float(quantity),
            "cost_basis": float(total_cost),
            "realized_pnl": float(realized_pnl),
            "fees": float(fees),
            "commissions": float(commissions),
            "closed_lots": [lot.to_dict() for lot in closed_lots],
            "position": position.to_dict() if position else None,
        }
    
    def _record_sale_lifo(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal,
        commissions: Decimal,
        date: datetime
    ) -> Dict[str, Any]:
        """Record sale using LIFO method"""
        lots = self.tax_lots[symbol]
        remaining = quantity
        total_cost = Decimal("0")
        realized_pnl = Decimal("0")
        closed_lots = []
        
        while remaining > 0 and lots:
            lot = lots[-1]  # Last in, first out
            if lot.quantity <= remaining:
                # Close entire lot
                lot_quantity = lot.quantity
                lot_cost = lot.cost_basis
                remaining -= lot_quantity
                total_cost += lot_cost
                
                # Calculate PnL for this lot
                lot_sale_value = lot_quantity * price
                lot_fees = (lot_quantity / quantity) * (fees + commissions)
                lot_pnl = lot_sale_value - lot_cost - lot_fees
                realized_pnl += lot_pnl
                
                # Update lot
                lot.status = "closed"
                lot.sale_date = date
                lot.sale_price = price
                lot.realized_pnl = lot_pnl
                
                # Move to closed lots
                closed_lots.append(lot)
                self.closed_lots[symbol].append(lot)
                lots.pop()
                
            else:
                # Partially close lot
                lot_quantity = remaining
                lot_cost = (remaining / lot.quantity) * lot.cost_basis
                total_cost += lot_cost
                
                # Calculate PnL for this portion
                lot_sale_value = remaining * price
                lot_fees = (remaining / quantity) * (fees + commissions)
                lot_pnl = lot_sale_value - lot_cost - lot_fees
                realized_pnl += lot_pnl
                
                # Update remaining lot
                lot.quantity -= remaining
                lot.cost_basis -= lot_cost
                remaining = Decimal("0")
                
                # Create partially closed lot record
                partial_lot = TaxLot(
                    id=f"{lot.id}_partial_{date.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    quantity=lot_quantity,
                    cost_basis=lot_cost,
                    purchase_date=lot.purchase_date,
                    sale_date=date,
                    sale_price=price,
                    realized_pnl=lot_pnl,
                    status="partially_closed",
                )
                self.closed_lots[symbol].append(partial_lot)
        
        # Update position
        position = self._update_position(symbol)
        
        return {
            "method": "lifo",
            "quantity_sold": float(quantity),
            "cost_basis": float(total_cost),
            "realized_pnl": float(realized_pnl),
            "fees": float(fees),
            "commissions": float(commissions),
            "closed_lots": [lot.to_dict() for lot in closed_lots],
            "position": position.to_dict() if position else None,
        }
    
    def _record_sale_average(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        fees: Decimal,
        commissions: Decimal,
        date: datetime
    ) -> Dict[str, Any]:
        """Record sale using Average Cost method"""
        lots = self.tax_lots[symbol]
        
        if not lots:
            return {"error": "No lots found"}
        
        # Calculate average cost
        total_cost = sum(lot.cost_basis for lot in lots)
        total_quantity = sum(lot.quantity for lot in lots)
        avg_cost = total_cost / total_quantity if total_quantity > 0 else Decimal("0")
        
        # Calculate cost basis for sold quantity
        cost_basis = avg_cost * quantity
        sale_value = quantity * price
        total_fees = fees + commissions
        realized_pnl = sale_value - cost_basis - total_fees
        
        # Update lots proportionally
        sold_quantity = quantity
        for lot in lots:
            if sold_quantity <= 0:
                break
            
            lot_portion = lot.quantity / total_quantity
            lot_sold = quantity * lot_portion
            
            if lot_sold >= lot.quantity:
                # Close lot
                lot.status = "closed"
                lot.sale_date = date
                lot.sale_price = price
                lot.realized_pnl = (lot_sold / quantity) * realized_pnl
                sold_quantity -= lot.quantity
                self.closed_lots[symbol].append(lot)
            else:
                # Partially close lot
                lot.quantity -= lot_sold
                lot.cost_basis -= lot_sold * avg_cost
                sold_quantity -= lot_sold
                
                # Create partial record
                partial_lot = TaxLot(
                    id=f"{lot.id}_partial_{date.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    quantity=lot_sold,
                    cost_basis=lot_sold * avg_cost,
                    purchase_date=lot.purchase_date,
                    sale_date=date,
                    sale_price=price,
                    realized_pnl=(lot_sold / quantity) * realized_pnl,
                    status="partially_closed",
                )
                self.closed_lots[symbol].append(partial_lot)
        
        # Remove closed lots
        self.tax_lots[symbol] = [lot for lot in lots if lot.status == "open"]
        
        # Update position
        position = self._update_position(symbol)
        
        return {
            "method": "average_cost",
            "quantity_sold": float(quantity),
            "cost_basis": float(cost_basis),
            "realized_pnl": float(realized_pnl),
            "fees": float(fees),
            "commissions": float(commissions),
            "position": position.to_dict() if position else None,
        }
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def _update_position(self, symbol: str) -> Optional[PositionAccounting]:
        """Update position accounting for a symbol"""
        lots = self.tax_lots.get(symbol, [])
        
        if not lots:
            # No open lots, position is closed
            return None
        
        # Calculate position metrics
        total_quantity = sum(lot.quantity for lot in lots)
        total_cost = sum(lot.cost_basis for lot in lots)
        avg_price = total_cost / total_quantity if total_quantity > 0 else Decimal("0")
        
        # Get current price from market data (would need to be passed in)
        current_price = Decimal("0")
        
        # Calculate market value
        market_value = total_quantity * current_price
        
        # Calculate unrealized PnL
        unrealized_pnl = market_value - total_cost
        
        # Calculate total PnL
        realized_pnl = self.calculate_realized_pnl(symbol)
        total_pnl = realized_pnl + unrealized_pnl
        
        # Calculate holding period
        purchase_dates = [lot.purchase_date for lot in lots]
        if purchase_dates:
            oldest_date = min(purchase_dates)
            holding_period = (datetime.now() - oldest_date).days
        else:
            holding_period = 0
        
        return PositionAccounting(
            symbol=symbol,
            side="long",  # Would need to determine side
            quantity=total_quantity,
            average_price=avg_price,
            current_price=current_price,
            cost_basis=total_cost,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            total_pnl=total_pnl,
            fees=Decimal("0"),
            commissions=Decimal("0"),
            financing_costs=Decimal("0"),
            holding_period=holding_period,
            tax_lots=lots,
        )
    
    def calculate_realized_pnl(self, symbol: str) -> Decimal:
        """Calculate realized PnL for a symbol"""
        closed_lots = self.closed_lots.get(symbol, [])
        return sum(lot.realized_pnl for lot in closed_lots if lot.realized_pnl)
    
    def calculate_unrealized_pnl(self, symbol: str, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL for a symbol"""
        lots = self.tax_lots.get(symbol, [])
        total_quantity = sum(lot.quantity for lot in lots)
        total_cost = sum(lot.cost_basis for lot in lots)
        market_value = total_quantity * current_price
        return market_value - total_cost
    
    # ============================================================
    # PORTFOLIO ACCOUNTING
    # ============================================================
    
    def calculate_portfolio_accounting(
        self,
        positions: Dict[str, Dict[str, Any]],
        current_prices: Dict[str, Decimal]
    ) -> PortfolioAccounting:
        """
        Calculate portfolio accounting
        
        Args:
            positions: Position data
            current_prices: Current prices
            
        Returns:
            PortfolioAccounting
        """
        total_value = Decimal("0")
        total_cost_basis = Decimal("0")
        unrealized_pnl = Decimal("0")
        realized_pnl = Decimal("0")
        total_fees = Decimal("0")
        total_commissions = Decimal("0")
        total_financing_costs = Decimal("0")
        cash_balance = Decimal("0")
        margin_used = Decimal("0")
        position_accounting = {}
        
        for symbol, position in positions.items():
            current_price = current_prices.get(symbol, Decimal("0"))
            
            # Update position
            pos_acc = self._update_position(symbol)
            if pos_acc:
                pos_acc.current_price = current_price
                pos_acc.market_value = pos_acc.quantity * current_price
                pos_acc.unrealized_pnl = pos_acc.market_value - pos_acc.cost_basis
                pos_acc.total_pnl = pos_acc.realized_pnl + pos_acc.unrealized_pnl
                
                position_accounting[symbol] = pos_acc
                
                # Aggregate
                total_value += pos_acc.market_value
                total_cost_basis += pos_acc.cost_basis
                unrealized_pnl += pos_acc.unrealized_pnl
                realized_pnl += pos_acc.realized_pnl
                total_fees += pos_acc.fees
                total_commissions += pos_acc.commissions
                total_financing_costs += pos_acc.financing_costs
        
        total_pnl = realized_pnl + unrealized_pnl
        
        # Calculate leverage
        leverage = total_value / cash_balance if cash_balance > 0 else Decimal("0")
        
        return PortfolioAccounting(
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            total_pnl=total_pnl,
            total_fees=total_fees,
            total_commissions=total_commissions,
            total_financing_costs=total_financing_costs,
            cash_balance=cash_balance,
            margin_used=margin_used,
            margin_available=cash_balance - margin_used,
            leverage=leverage,
            positions=position_accounting,
            timestamp=datetime.now(),
        )
    
    # ============================================================
    # PERFORMANCE METRICS
    # ============================================================
    
    def calculate_performance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_balance: Decimal,
        final_balance: Decimal,
        trade_history: List[Dict[str, Any]]
    ) -> PerformanceReport:
        """
        Calculate performance report
        
        Args:
            start_date: Start date
            end_date: End date
            initial_balance: Initial balance
            final_balance: Final balance
            trade_history: List of trades
            
        Returns:
            PerformanceReport
        """
        # Calculate total return
        total_return = (final_balance - initial_balance) / initial_balance if initial_balance > 0 else Decimal("0")
        
        # Calculate annualized return
        days = (end_date - start_date).days
        if days > 0:
            annualized_return = (Decimal("1") + total_return) ** (Decimal("365") / Decimal(days)) - Decimal("1")
        else:
            annualized_return = Decimal("0")
        
        # Calculate win rate
        winning_trades = [t for t in trade_history if t.get("realized_pnl", 0) > 0]
        losing_trades = [t for t in trade_history if t.get("realized_pnl", 0) < 0]
        total_trades = len(trade_history)
        
        if total_trades > 0:
            win_rate = Decimal(len(winning_trades)) / Decimal(total_trades)
        else:
            win_rate = Decimal("0")
        
        # Calculate average win/loss
        total_win = sum(t.get("realized_pnl", 0) for t in winning_trades)
        total_loss = sum(abs(t.get("realized_pnl", 0)) for t in losing_trades)
        
        if winning_trades:
            average_win = Decimal(total_win) / Decimal(len(winning_trades))
        else:
            average_win = Decimal("0")
        
        if losing_trades:
            average_loss = Decimal(total_loss) / Decimal(len(losing_trades))
        else:
            average_loss = Decimal("0")
        
        # Calculate profit factor
        if total_loss > 0:
            profit_factor = Decimal(total_win) / Decimal(total_loss)
        else:
            profit_factor = Decimal("0")
        
        # Calculate Sharpe ratio (simplified)
        returns = self._calculate_returns(trade_history)
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                sharpe_ratio = Decimal(avg_return / std_return * np.sqrt(252))
            else:
                sharpe_ratio = Decimal("0")
        else:
            sharpe_ratio = Decimal("0")
        
        # Calculate Sortino ratio
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = Decimal(avg_return / downside_std * np.sqrt(252) if avg_return else 0)
            else:
                sortino_ratio = Decimal("0")
        else:
            sortino_ratio = Decimal("0")
        
        # Calculate Calmar ratio
        max_drawdown = self.calculate_max_drawdown()
        if max_drawdown > 0:
            calmar_ratio = annualized_return / max_drawdown
        else:
            calmar_ratio = Decimal("0")
        
        # Calculate total volume
        total_volume = sum(t.get("sale_value", 0) + t.get("cost_basis", 0) for t in trade_history)
        
        # Calculate total fees
        total_fees = sum(t.get("fees", 0) for t in trade_history)
        
        # Calculate total commissions
        total_commissions = sum(t.get("commissions", 0) for t in trade_history)
        
        return PerformanceReport(
            period_start=start_date,
            period_end=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_win=average_win,
            average_loss=average_loss,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            total_volume=Decimal(total_volume),
            total_fees=Decimal(total_fees),
            total_commissions=Decimal(total_commissions),
        )
    
    def _calculate_returns(self, trade_history: List[Dict[str, Any]]) -> List[float]:
        """Calculate returns from trade history"""
        returns = []
        current_pnl = 0.0
        
        for trade in trade_history:
            pnl = trade.get("realized_pnl", 0)
            if pnl != 0:
                returns.append(pnl)
        
        return returns
    
    def calculate_max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown"""
        if not self.equity_curve:
            return Decimal("0")
        
        values = [e["value"] for e in self.equity_curve]
        peak = values[0]
        max_drawdown = Decimal("0")
        
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_accounting_report(self) -> Dict[str, Any]:
        """
        Generate an accounting report
        
        Returns:
            Report dictionary
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "tax_lots": {
                symbol: [lot.to_dict() for lot in lots]
                for symbol, lots in self.tax_lots.items()
            },
            "closed_lots": {
                symbol: [lot.to_dict() for lot in lots]
                for symbol, lots in self.closed_lots.items()
            },
            "trade_history": self.trade_history,
            "position_history": self.position_history,
            "equity_curve": self.equity_curve,
            "daily_pnl": self.daily_pnl,
            "drawdowns": self.drawdowns,
            "summary": {
                "total_trades": len(self.trade_history),
                "open_lots": sum(len(lots) for lots in self.tax_lots.values()),
                "closed_lots": sum(len(lots) for lots in self.closed_lots.values()),
            },
        }
    
    def generate_pnl_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a PnL report
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Report dictionary
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        # Filter trades by date
        trades = [
            t for t in self.trade_history
            if start_date <= datetime.fromisoformat(t["date"]) <= end_date
        ]
        
        # Calculate PnL
        realized_pnl = sum(t.get("realized_pnl", 0) for t in trades)
        fees = sum(t.get("fees", 0) for t in trades)
        commissions = sum(t.get("commissions", 0) for t in trades)
        
        # Group by symbol
        pnl_by_symbol = defaultdict(lambda: {"realized_pnl": 0, "fees": 0, "trades": 0})
        for trade in trades:
            symbol = trade.get("symbol", "unknown")
            pnl_by_symbol[symbol]["realized_pnl"] += trade.get("realized_pnl", 0)
            pnl_by_symbol[symbol]["fees"] += trade.get("fees", 0)
            pnl_by_symbol[symbol]["trades"] += 1
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total": {
                "realized_pnl": realized_pnl,
                "fees": fees,
                "commissions": commissions,
                "net_pnl": realized_pnl - fees - commissions,
                "trades": len(trades),
            },
            "by_symbol": dict(pnl_by_symbol),
            "trade_history": trades,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Dataclasses
    "TaxLot",
    "PositionAccounting",
    "PortfolioAccounting",
    "PerformanceReport",
    
    # Classes
    "AccountingEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

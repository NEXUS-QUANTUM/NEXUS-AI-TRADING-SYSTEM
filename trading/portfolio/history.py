"""
NEXUS AI TRADING SYSTEM - Portfolio History Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/history.py
Description: Comprehensive portfolio history tracking with full API integration
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.portfolio_config import PortfolioConfig
from shared.constants.trading_constants import TIME_FRAMES
from shared.helpers.trading_helpers import (
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Trade, PortfolioSnapshot
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class HistoryPeriod(str, Enum):
    """History periods"""
    TODAY = "today"
    YESTERDAY = "yesterday"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    ALL = "all"
    CUSTOM = "custom"


class HistoryGranularity(str, Enum):
    """History granularity"""
    MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    HOUR = "1h"
    FOUR_HOURS = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1m"


class ExportFormat(str, Enum):
    """Export formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PARQUET = "parquet"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class HistoryRequest(BaseModel):
    """Request model for history"""
    portfolio_id: str
    period: HistoryPeriod = HistoryPeriod.MONTH
    granularity: HistoryGranularity = HistoryGranularity.DAY
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_positions: bool = True
    include_trades: bool = True
    include_snapshots: bool = True
    include_metrics: bool = True
    symbols: Optional[List[str]] = None
    limit: int = 1000
    offset: int = 0


class HistoryResponse(BaseModel):
    """Response model for history"""
    portfolio_id: str
    period: HistoryPeriod
    granularity: HistoryGranularity
    start_date: datetime
    end_date: datetime
    total_records: int
    snapshots: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    positions: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TradeHistoryResponse(BaseModel):
    """Response model for trade history"""
    portfolio_id: str
    total_trades: int
    trades: List[Dict[str, Any]]
    summary: Dict[str, Any]
    performance: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionHistoryResponse(BaseModel):
    """Response model for position history"""
    portfolio_id: str
    total_positions: int
    positions: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    """Request model for export"""
    portfolio_id: str
    format: ExportFormat = ExportFormat.CSV
    period: HistoryPeriod = HistoryPeriod.MONTH
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_trades: bool = True
    include_positions: bool = True
    include_snapshots: bool = True
    include_metrics: bool = True


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HistoryContext:
    """Context for history"""
    portfolio_id: str
    period: HistoryPeriod
    granularity: HistoryGranularity
    start_date: datetime
    end_date: datetime
    snapshots: List[Any]
    trades: List[Any]
    positions: List[Any]
    symbols: List[str]
    limit: int
    offset: int


@dataclass
class PerformanceSummary:
    """Performance summary"""
    total_pnl: float
    total_pnl_pct: float
    avg_daily_pnl: float
    max_daily_pnl: float
    min_daily_pnl: float
    winning_days: int
    losing_days: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int


# =============================================================================
# PORTFOLIO HISTORY
# =============================================================================

class PortfolioHistory:
    """
    Comprehensive Portfolio History Tracking with full API integration.
    
    Features:
    - Historical snapshots
    - Trade history
    - Position history
    - Performance metrics
    - Export capabilities
    - Custom date ranges
    - Multiple granularities
    - Data aggregation
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize PortfolioHistory.
        
        Args:
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Cache
        self._history_cache: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self._performance_cache: Dict[str, PerformanceSummary] = {}
        
        logger.info("PortfolioHistory initialized")

    # =========================================================================
    # History Retrieval
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_history(
        self,
        request: HistoryRequest
    ) -> HistoryResponse:
        """
        Get portfolio history.
        
        Args:
            request: History request
            
        Returns:
            HistoryResponse: History data
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Build context
            context = await self._build_context(request)
            
            # Get snapshots
            snapshots = []
            if request.include_snapshots:
                snapshots = await self._get_snapshots(context)
            
            # Get trades
            trades = []
            if request.include_trades:
                trades = await self._get_trades(context)
            
            # Get positions
            positions = []
            if request.include_positions:
                positions = await self._get_positions(context)
            
            # Calculate metrics
            metrics = {}
            if request.include_metrics:
                metrics = await self._calculate_metrics(context, snapshots, trades)
            
            # Calculate summary
            summary = self._calculate_summary(snapshots, trades, positions)
            
            # Create response
            response = HistoryResponse(
                portfolio_id=request.portfolio_id,
                period=request.period,
                granularity=request.granularity,
                start_date=context.start_date,
                end_date=context.end_date,
                total_records=len(snapshots) + len(trades) + len(positions),
                snapshots=[s.__dict__ if hasattr(s, '__dict__') else s for s in snapshots],
                trades=[t.__dict__ if hasattr(t, '__dict__') else t for t in trades],
                positions=[p.__dict__ if hasattr(p, '__dict__') else p for p in positions],
                metrics=metrics,
                summary=summary,
                metadata=request.metadata
            )
            
            # Cache response
            cache_key = f"{request.portfolio_id}_{request.period.value}_{request.granularity.value}"
            self._history_cache[cache_key] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"History retrieved for {request.portfolio_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error getting history: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"History retrieval failed: {str(e)}"
            )

    async def _validate_request(self, request: HistoryRequest) -> None:
        """Validate history request"""
        if request.start_date and request.end_date:
            if request.start_date > request.end_date:
                raise ValueError("Start date must be before end date")
        
        if request.limit < 1:
            raise ValueError("Limit must be at least 1")
        
        if request.offset < 0:
            raise ValueError("Offset must be non-negative")

    async def _build_context(self, request: HistoryRequest) -> HistoryContext:
        """Build history context"""
        # Set date range
        end_date = request.end_date or datetime.utcnow()
        start_date = request.start_date
        
        if not start_date:
            # Map period to timedelta
            period_map = {
                HistoryPeriod.TODAY: timedelta(days=1),
                HistoryPeriod.YESTERDAY: timedelta(days=2),
                HistoryPeriod.WEEK: timedelta(days=7),
                HistoryPeriod.MONTH: timedelta(days=30),
                HistoryPeriod.QUARTER: timedelta(days=90),
                HistoryPeriod.YEAR: timedelta(days=365)
            }
            
            if request.period == HistoryPeriod.TODAY:
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif request.period == HistoryPeriod.YESTERDAY:
                start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                delta = period_map.get(request.period, timedelta(days=30))
                start_date = end_date - delta
        
        # Get symbols
        symbols = request.symbols or []
        
        return HistoryContext(
            portfolio_id=request.portfolio_id,
            period=request.period,
            granularity=request.granularity,
            start_date=start_date,
            end_date=end_date,
            snapshots=[],
            trades=[],
            positions=[],
            symbols=symbols,
            limit=request.limit,
            offset=request.offset
        )

    # =========================================================================
    # Data Retrieval
    # =========================================================================

    async def _get_snapshots(self, context: HistoryContext) -> List[Any]:
        """Get portfolio snapshots"""
        try:
            snapshots = await self.portfolio_repo.get_snapshots(
                context.portfolio_id,
                start_date=context.start_date,
                end_date=context.end_date,
                limit=context.limit,
                offset=context.offset
            )
            
            # Filter by symbols if specified
            if context.symbols and snapshots:
                snapshots = [
                    s for s in snapshots
                    if hasattr(s, 'symbol') and s.symbol in context.symbols
                ]
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Error getting snapshots: {e}")
            return []

    async def _get_trades(self, context: HistoryContext) -> List[Any]:
        """Get trades"""
        try:
            trades = await self.trade_repo.get_by_portfolio_id(
                context.portfolio_id,
                start_date=context.start_date,
                end_date=context.end_date,
                limit=context.limit,
                offset=context.offset
            )
            
            # Filter by symbols if specified
            if context.symbols and trades:
                trades = [t for t in trades if t.symbol in context.symbols]
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []

    async def _get_positions(self, context: HistoryContext) -> List[Any]:
        """Get positions"""
        try:
            positions = await self.position_repo.get_by_portfolio_id(
                context.portfolio_id
            )
            
            # Filter by symbols if specified
            if context.symbols and positions:
                positions = [p for p in positions if p.symbol in context.symbols]
            
            # Filter by date range
            if positions:
                positions = [
                    p for p in positions
                    if p.created_at >= context.start_date and p.created_at <= context.end_date
                ]
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    # =========================================================================
    # Metrics Calculation
    # =========================================================================

    async def _calculate_metrics(
        self,
        context: HistoryContext,
        snapshots: List[Any],
        trades: List[Any]
    ) -> Dict[str, Any]:
        """Calculate metrics from history"""
        metrics = {}
        
        # Calculate from trades
        if trades:
            # Win/Loss stats
            winning_trades = [t for t in trades if float(t.pnl) > 0]
            losing_trades = [t for t in trades if float(t.pnl) < 0]
            
            metrics['total_trades'] = len(trades)
            metrics['winning_trades'] = len(winning_trades)
            metrics['losing_trades'] = len(losing_trades)
            metrics['win_rate'] = len(winning_trades) / len(trades) if trades else 0
            
            total_pnl = sum(float(t.pnl) for t in trades)
            metrics['total_pnl'] = total_pnl
            
            gross_profit = sum(float(t.pnl) for t in winning_trades)
            gross_loss = abs(sum(float(t.pnl) for t in losing_trades))
            metrics['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            metrics['avg_pnl'] = total_pnl / len(trades) if trades else 0
            metrics['avg_win'] = gross_profit / len(winning_trades) if winning_trades else 0
            metrics['avg_loss'] = gross_loss / len(losing_trades) if losing_trades else 0
            
            # Sharpe ratio
            returns = []
            for i in range(1, len(trades)):
                if hasattr(trades[i], 'pnl') and hasattr(trades[i-1], 'pnl'):
                    pnl_diff = float(trades[i].pnl) - float(trades[i-1].pnl)
                    prev_pnl = abs(float(trades[i-1].pnl))
                    if prev_pnl > 0:
                        returns.append(pnl_diff / prev_pnl)
            
            if returns:
                metrics['sharpe_ratio'] = calculate_sharpe_ratio(returns)
                metrics['sortino_ratio'] = calculate_sortino_ratio(returns)
        
        # Calculate from snapshots
        if snapshots:
            values = [float(s.total_value) for s in snapshots]
            
            if values:
                # Volatility
                returns = [(values[i] - values[i-1]) / values[i-1] 
                          for i in range(1, len(values))]
                metrics['volatility'] = np.std(returns) * np.sqrt(252) if returns else 0
                
                # Drawdown
                metrics['max_drawdown'] = calculate_drawdown(values)
                
                # Calmar ratio
                if metrics.get('max_drawdown', 0) > 0:
                    annual_return = np.mean(returns) * 252 if returns else 0
                    metrics['calmar_ratio'] = annual_return / metrics['max_drawdown']
        
        return metrics

    def _calculate_summary(
        self,
        snapshots: List[Any],
        trades: List[Any],
        positions: List[Any]
    ) -> Dict[str, Any]:
        """Calculate summary statistics"""
        summary = {
            'total_snapshots': len(snapshots),
            'total_trades': len(trades),
            'total_positions': len(positions)
        }
        
        # Trade summary
        if trades:
            total_pnl = sum(float(t.pnl) for t in trades)
            summary['total_pnl'] = total_pnl
            summary['avg_pnl'] = total_pnl / len(trades) if trades else 0
            
            winning_trades = [t for t in trades if float(t.pnl) > 0]
            losing_trades = [t for t in trades if float(t.pnl) < 0]
            summary['winning_trades'] = len(winning_trades)
            summary['losing_trades'] = len(losing_trades)
            summary['win_rate'] = len(winning_trades) / len(trades) if trades else 0
        
        # Position summary
        if positions:
            summary['total_position_value'] = sum(float(p.size) * float(p.entry_price) for p in positions)
            summary['avg_position_value'] = summary['total_position_value'] / len(positions) if positions else 0
        
        # Snapshot summary
        if snapshots:
            values = [float(s.total_value) for s in snapshots]
            summary['start_value'] = values[0] if values else 0
            summary['end_value'] = values[-1] if values else 0
            summary['max_value'] = max(values) if values else 0
            summary['min_value'] = min(values) if values else 0
            summary['total_return'] = (values[-1] - values[0]) / values[0] if values and values[0] > 0 else 0
        
        return summary

    # =========================================================================
    # Trade History
    # =========================================================================

    async def get_trade_history(
        self,
        portfolio_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> TradeHistoryResponse:
        """
        Get trade history.
        
        Args:
            portfolio_id: Portfolio ID
            start_date: Start date
            end_date: End date
            symbol: Symbol filter
            limit: Maximum records
            offset: Offset
            
        Returns:
            TradeHistoryResponse: Trade history
        """
        try:
            # Get trades
            trades = await self.trade_repo.get_by_portfolio_id(
                portfolio_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit + offset,
                offset=offset
            )
            
            # Filter by symbol
            if symbol:
                trades = [t for t in trades if t.symbol == symbol]
            
            # Calculate summary
            total_trades = len(trades)
            total_pnl = sum(float(t.pnl) for t in trades)
            
            winning_trades = [t for t in trades if float(t.pnl) > 0]
            losing_trades = [t for t in trades if float(t.pnl) < 0]
            
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            
            gross_profit = sum(float(t.pnl) for t in winning_trades)
            gross_loss = abs(sum(float(t.pnl) for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Performance
            performance = {
                'total_pnl': total_pnl,
                'avg_pnl': total_pnl / total_trades if total_trades > 0 else 0,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'avg_win': gross_profit / len(winning_trades) if winning_trades else 0,
                'avg_loss': gross_loss / len(losing_trades) if losing_trades else 0,
                'best_trade': max(float(t.pnl) for t in trades) if trades else 0,
                'worst_trade': min(float(t.pnl) for t in trades) if trades else 0
            }
            
            return TradeHistoryResponse(
                portfolio_id=portfolio_id,
                total_trades=total_trades,
                trades=[t.__dict__ for t in trades],
                summary={
                    'start_date': start_date,
                    'end_date': end_date,
                    'symbol': symbol
                },
                performance=performance
            )
            
        except Exception as e:
            logger.error(f"Error getting trade history: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Trade history retrieval failed: {str(e)}"
            )

    # =========================================================================
    # Position History
    # =========================================================================

    async def get_position_history(
        self,
        portfolio_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> PositionHistoryResponse:
        """
        Get position history.
        
        Args:
            portfolio_id: Portfolio ID
            start_date: Start date
            end_date: End date
            symbol: Symbol filter
            status: Position status
            
        Returns:
            PositionHistoryResponse: Position history
        """
        try:
            # Get positions
            positions = await self.position_repo.get_by_portfolio_id(portfolio_id)
            
            # Filter by symbol
            if symbol:
                positions = [p for p in positions if p.symbol == symbol]
            
            # Filter by status
            if status:
                positions = [p for p in positions if p.status == status]
            
            # Filter by date range
            if start_date:
                positions = [p for p in positions if p.created_at >= start_date]
            if end_date:
                positions = [p for p in positions if p.created_at <= end_date]
            
            # Calculate summary
            total_positions = len(positions)
            total_value = sum(float(p.size) * float(p.entry_price) for p in positions)
            
            open_positions = [p for p in positions if p.status == 'open']
            closed_positions = [p for p in positions if p.status == 'closed']
            
            return PositionHistoryResponse(
                portfolio_id=portfolio_id,
                total_positions=total_positions,
                positions=[p.__dict__ for p in positions],
                summary={
                    'total_value': total_value,
                    'avg_value': total_value / total_positions if total_positions > 0 else 0,
                    'open_positions': len(open_positions),
                    'closed_positions': len(closed_positions),
                    'start_date': start_date,
                    'end_date': end_date,
                    'symbol': symbol,
                    'status': status
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting position history: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Position history retrieval failed: {str(e)}"
            )

    # =========================================================================
    # Export
    # =========================================================================

    async def export_history(
        self,
        request: ExportRequest
    ) -> Union[str, bytes]:
        """
        Export portfolio history.
        
        Args:
            request: Export request
            
        Returns:
            Union[str, bytes]: Exported data
        """
        try:
            # Get history
            history_request = HistoryRequest(
                portfolio_id=request.portfolio_id,
                period=request.period,
                start_date=request.start_date,
                end_date=request.end_date,
                include_trades=request.include_trades,
                include_positions=request.include_positions,
                include_snapshots=request.include_snapshots,
                include_metrics=request.include_metrics
            )
            
            history = await self.get_history(history_request)
            
            # Convert to DataFrame
            data = {}
            
            if request.include_snapshots and history.snapshots:
                data['snapshots'] = pd.DataFrame(history.snapshots)
            
            if request.include_trades and history.trades:
                data['trades'] = pd.DataFrame(history.trades)
            
            if request.include_positions and history.positions:
                data['positions'] = pd.DataFrame(history.positions)
            
            if request.include_metrics and history.metrics:
                data['metrics'] = pd.DataFrame([history.metrics])
            
            # Export based on format
            if request.format == ExportFormat.CSV:
                return self._export_csv(data)
            elif request.format == ExportFormat.JSON:
                return self._export_json(data)
            elif request.format == ExportFormat.EXCEL:
                return await self._export_excel(data)
            elif request.format == ExportFormat.PARQUET:
                return await self._export_parquet(data)
            else:
                return self._export_csv(data)
            
        except Exception as e:
            logger.error(f"Error exporting history: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {str(e)}"
            )

    def _export_csv(self, data: Dict[str, pd.DataFrame]) -> str:
        """Export to CSV"""
        output = []
        
        for name, df in data.items():
            if not df.empty:
                output.append(f"# {name.upper()}")
                output.append(df.to_csv(index=False))
                output.append("")
        
        return '\n'.join(output)

    def _export_json(self, data: Dict[str, pd.DataFrame]) -> str:
        """Export to JSON"""
        import json
        
        output = {}
        for name, df in data.items():
            if not df.empty:
                output[name] = df.to_dict(orient='records')
        
        return json.dumps(output, default=str, indent=2)

    async def _export_excel(self, data: Dict[str, pd.DataFrame]) -> bytes:
        """Export to Excel"""
        import io
        import openpyxl
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for name, df in data.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=name[:31], index=False)
        
        return output.getvalue()

    async def _export_parquet(self, data: Dict[str, pd.DataFrame]) -> bytes:
        """Export to Parquet"""
        import io
        
        output = io.BytesIO()
        
        for name, df in data.items():
            if not df.empty:
                df.to_parquet(output, index=False)
        
        return output.getvalue()

    # =========================================================================
    # Performance Summary
    # =========================================================================

    async def get_performance_summary(
        self,
        portfolio_id: str,
        period: HistoryPeriod = HistoryPeriod.MONTH
    ) -> PerformanceSummary:
        """
        Get performance summary.
        
        Args:
            portfolio_id: Portfolio ID
            period: Period
            
        Returns:
            PerformanceSummary: Performance summary
        """
        try:
            # Get history
            request = HistoryRequest(
                portfolio_id=portfolio_id,
                period=period,
                include_trades=True,
                include_snapshots=True,
                include_metrics=True
            )
            
            history = await self.get_history(request)
            
            # Calculate performance
            total_pnl = history.summary.get('total_pnl', 0)
            total_return = history.summary.get('total_return', 0)
            
            # Daily PnL
            daily_pnl = []
            if history.snapshots:
                values = [float(s.get('total_value', 0)) for s in history.snapshots]
                for i in range(1, len(values)):
                    if values[i-1] > 0:
                        daily_pnl.append((values[i] - values[i-1]) / values[i-1])
            
            metrics = history.metrics
            
            return PerformanceSummary(
                total_pnl=total_pnl,
                total_pnl_pct=total_return * 100,
                avg_daily_pnl=np.mean(daily_pnl) if daily_pnl else 0,
                max_daily_pnl=max(daily_pnl) if daily_pnl else 0,
                min_daily_pnl=min(daily_pnl) if daily_pnl else 0,
                winning_days=sum(1 for d in daily_pnl if d > 0),
                losing_days=sum(1 for d in daily_pnl if d < 0),
                win_rate=history.summary.get('win_rate', 0),
                profit_factor=metrics.get('profit_factor', 0),
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                sortino_ratio=metrics.get('sortino_ratio', 0),
                calmar_ratio=metrics.get('calmar_ratio', 0),
                max_drawdown=metrics.get('max_drawdown', 0),
                max_drawdown_duration=self._calculate_drawdown_duration(history.snapshots)
            )
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return PerformanceSummary(
                total_pnl=0,
                total_pnl_pct=0,
                avg_daily_pnl=0,
                max_daily_pnl=0,
                min_daily_pnl=0,
                winning_days=0,
                losing_days=0,
                win_rate=0,
                profit_factor=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                calmar_ratio=0,
                max_drawdown=0,
                max_drawdown_duration=0
            )

    def _calculate_drawdown_duration(
        self,
        snapshots: List[Dict[str, Any]]
    ) -> int:
        """Calculate maximum drawdown duration in days"""
        if not snapshots:
            return 0
        
        values = [float(s.get('total_value', 0)) for s in snapshots]
        
        max_duration = 0
        current_duration = 0
        peak = values[0]
        
        for value in values:
            if value > peak:
                peak = value
                current_duration = 0
            else:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
        
        return max_duration

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the history module"""
        self._history_cache.clear()
        self._performance_cache.clear()
        logger.info("PortfolioHistory closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/api/v1/portfolio/history", tags=["Portfolio History"])


async def get_history() -> PortfolioHistory:
    """Dependency to get PortfolioHistory instance"""
    return PortfolioHistory()


@router.post("/", response_model=HistoryResponse)
async def get_history(
    request: HistoryRequest,
    history: PortfolioHistory = Depends(get_history)
):
    """Get portfolio history"""
    return await history.get_history(request)


@router.get("/{portfolio_id}/trades")
async def get_trade_history(
    portfolio_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    history: PortfolioHistory = Depends(get_history)
):
    """Get trade history"""
    return await history.get_trade_history(
        portfolio_id,
        start_date,
        end_date,
        symbol,
        limit,
        offset
    )


@router.get("/{portfolio_id}/positions")
async def get_position_history(
    portfolio_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    history: PortfolioHistory = Depends(get_history)
):
    """Get position history"""
    return await history.get_position_history(
        portfolio_id,
        start_date,
        end_date,
        symbol,
        status
    )


@router.get("/{portfolio_id}/performance")
async def get_performance_summary(
    portfolio_id: str,
    period: HistoryPeriod = Query(HistoryPeriod.MONTH),
    history: PortfolioHistory = Depends(get_history)
):
    """Get performance summary"""
    return await history.get_performance_summary(portfolio_id, period)


@router.post("/export")
async def export_history(
    request: ExportRequest,
    history: PortfolioHistory = Depends(get_history)
):
    """Export portfolio history"""
    data = await history.export_history(request)
    
    content_type = {
        ExportFormat.CSV: 'text/csv',
        ExportFormat.JSON: 'application/json',
        ExportFormat.EXCEL: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ExportFormat.PARQUET: 'application/octet-stream'
    }.get(request.format, 'text/csv')
    
    extension = {
        ExportFormat.CSV: 'csv',
        ExportFormat.JSON: 'json',
        ExportFormat.EXCEL: 'xlsx',
        ExportFormat.PARQUET: 'parquet'
    }.get(request.format, 'csv')
    
    filename = f"portfolio_history_{request.portfolio_id}.{extension}"
    
    return Response(
        content=data if isinstance(data, bytes) else data.encode('utf-8'),
        media_type=content_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioHistory',
    'HistoryPeriod',
    'HistoryGranularity',
    'ExportFormat',
    'HistoryRequest',
    'HistoryResponse',
    'TradeHistoryResponse',
    'PositionHistoryResponse',
    'ExportRequest',
    'HistoryContext',
    'PerformanceSummary',
    'router'
]

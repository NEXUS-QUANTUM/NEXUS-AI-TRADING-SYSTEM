"""
NEXUS AI TRADING SYSTEM - Paper Trading Replay Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_replay.py
Description: Paper trading market replay with full API integration
"""

import asyncio
import json
import logging
import time
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
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger

# Paper trading imports
from trading.paper_trading.paper_account import PaperTradingAccount
from trading.paper_trading.paper_market import PaperTradingMarket
from trading.paper_trading.paper_orders import PaperTradingOrders
from trading.paper_trading.paper_portfolio import PaperTradingPortfolio

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ReplayStatus(str, Enum):
    """Replay status"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class ReplaySpeed(str, Enum):
    """Replay speeds"""
    REAL_TIME = "real_time"
    FAST = "fast"  # 2x speed
    VERY_FAST = "very_fast"  # 5x speed
    ULTRA_FAST = "ultra_fast"  # 10x speed
    MAX = "max"  # Maximum speed


class DataSource(str, Enum):
    """Data sources"""
    HISTORICAL = "historical"
    EXTERNAL = "external"
    GENERATED = "generated"
    CUSTOM = "custom"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ReplayRequest(BaseModel):
    """Request model for replay"""
    account_id: str
    symbol: str
    start_date: datetime
    end_date: datetime
    speed: ReplaySpeed = ReplaySpeed.REAL_TIME
    data_source: DataSource = DataSource.HISTORICAL
    data_file: Optional[str] = None
    skip_initialization: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('start_date')
    def validate_start(cls, v, values):
        if 'end_date' in values and v > values['end_date']:
            raise ValueError("Start date must be before end date")
        return v


class ReplayResponse(BaseModel):
    """Response model for replay"""
    replay_id: str
    account_id: str
    symbol: str
    status: ReplayStatus
    speed: ReplaySpeed
    start_date: datetime
    end_date: datetime
    current_date: datetime
    progress: float  # 0-100
    total_bars: int
    processed_bars: int
    trades_executed: int
    pnl: float
    started_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReplayBarData(BaseModel):
    """Replay bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


class ReplaySummaryResponse(BaseModel):
    """Response model for replay summary"""
    replay_id: str
    symbol: str
    start_date: datetime
    end_date: datetime
    total_bars: int
    processed_bars: int
    execution_time: float
    trades_executed: int
    final_pnl: float
    final_equity: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ReplayState:
    """Replay state"""
    replay_id: str
    account_id: str
    symbol: str
    status: ReplayStatus
    speed: ReplaySpeed
    start_date: datetime
    end_date: datetime
    current_date: datetime
    total_bars: int
    processed_bars: int
    trades_executed: int
    pnl: float
    equity: float
    bars: List[ReplayBarData]
    started_at: datetime
    updated_at: datetime


@dataclass
class ReplayBar:
    """Replay bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int
    bid: float
    ask: float


# =============================================================================
# PAPER TRADING REPLAY
# =============================================================================

class PaperTradingReplay:
    """
    Paper Trading Market Replay with full API integration.
    
    Features:
    - Historical data replay
    - Variable playback speed
    - Real-time simulation
    - Bar-by-bar processing
    - Performance metrics
    - PnL tracking
    - Trade execution
    - Portfolio simulation
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        paper_account: Optional[PaperTradingAccount] = None,
        paper_market: Optional[PaperTradingMarket] = None,
        paper_orders: Optional[PaperTradingOrders] = None,
        paper_portfolio: Optional[PaperTradingPortfolio] = None
    ):
        """
        Initialize PaperTradingReplay.
        
        Args:
            config: Paper trading configuration
            paper_account: Paper trading account
            paper_market: Paper trading market
            paper_orders: Paper trading orders
            paper_portfolio: Paper trading portfolio
        """
        self.config = config or PaperTradingConfig()
        self.paper_account = paper_account or PaperTradingAccount()
        self.paper_market = paper_market or PaperTradingMarket()
        self.paper_orders = paper_orders or PaperTradingOrders()
        self.paper_portfolio = paper_portfolio or PaperTradingPortfolio()
        
        # Replay storage
        self._replays: Dict[str, ReplayState] = {}
        self._replay_info: Dict[str, Dict[str, Any]] = {}
        
        # Data cache
        self._data_cache: Dict[str, List[ReplayBar]] = {}
        
        # Replay counter
        self._replay_counter: int = 0
        
        # Monitoring
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("PaperTradingReplay initialized")

    # =========================================================================
    # Replay Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def start_replay(
        self,
        request: ReplayRequest
    ) -> ReplayResponse:
        """
        Start a replay.
        
        Args:
            request: Replay request
            
        Returns:
            ReplayResponse: Replay status
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Generate replay ID
            self._replay_counter += 1
            replay_id = f"replay_{int(time.time() * 1000)}_{self._replay_counter:06d}"
            
            # Load data
            bars = await self._load_data(request)
            
            if not bars:
                raise ValueError(f"No data available for {request.symbol}")
            
            # Create replay state
            state = ReplayState(
                replay_id=replay_id,
                account_id=request.account_id,
                symbol=request.symbol,
                status=ReplayStatus.INITIALIZING,
                speed=request.speed,
                start_date=request.start_date,
                end_date=request.end_date,
                current_date=request.start_date,
                total_bars=len(bars),
                processed_bars=0,
                trades_executed=0,
                pnl=0,
                equity=0,
                bars=bars,
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Store replay
            self._replays[replay_id] = state
            self._replay_info[replay_id] = {
                'account_id': request.account_id,
                'symbol': request.symbol,
                'data_source': request.data_source.value,
                'metadata': request.metadata
            }
            
            # Start replay
            await self._start_replay_loop(replay_id)
            
            logger.info(f"Replay {replay_id} started for {request.symbol}")
            return self._to_response(replay_id)
            
        except Exception as e:
            logger.error(f"Error starting replay: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Replay start failed: {str(e)}"
            )

    async def _validate_request(self, request: ReplayRequest) -> None:
        """Validate replay request"""
        if request.start_date >= request.end_date:
            raise ValueError("Start date must be before end date")
        
        # Validate account
        account = await self.paper_account.get_account(request.account_id)
        if not account:
            raise ValueError(f"Account {request.account_id} not found")

    async def _load_data(self, request: ReplayRequest) -> List[ReplayBar]:
        """Load replay data"""
        cache_key = f"{request.symbol}_{request.start_date}_{request.end_date}"
        
        # Check cache
        if cache_key in self._data_cache:
            return self._data_cache[cache_key]
        
        bars = []
        
        if request.data_source == DataSource.HISTORICAL:
            bars = await self._load_historical_data(request)
        elif request.data_source == DataSource.EXTERNAL:
            bars = await self._load_external_data(request)
        elif request.data_source == DataSource.GENERATED:
            bars = await self._load_generated_data(request)
        elif request.data_source == DataSource.CUSTOM:
            bars = await self._load_custom_data(request)
        else:
            bars = await self._load_historical_data(request)
        
        # Cache data
        self._data_cache[cache_key] = bars
        
        return bars

    async def _load_historical_data(
        self,
        request: ReplayRequest
    ) -> List[ReplayBar]:
        """Load historical data"""
        bars = []
        
        try:
            # Get from market data service or external source
            # For now, generate mock data
            bars = self._generate_mock_data(request)
        except Exception as e:
            logger.warning(f"Error loading historical data: {e}")
            bars = self._generate_mock_data(request)
        
        return bars

    async def _load_external_data(self, request: ReplayRequest) -> List[ReplayBar]:
        """Load external data"""
        # Load from external file or API
        # For now, fallback to generated data
        return self._generate_mock_data(request)

    async def _load_generated_data(self, request: ReplayRequest) -> List[ReplayBar]:
        """Load generated data"""
        return self._generate_mock_data(request)

    async def _load_custom_data(self, request: ReplayRequest) -> List[ReplayBar]:
        """Load custom data"""
        # Load from custom source
        # For now, fallback to generated data
        return self._generate_mock_data(request)

    def _generate_mock_data(self, request: ReplayRequest) -> List[ReplayBar]:
        """Generate mock bar data"""
        bars = []
        current_time = request.start_date
        price = 100.0
        
        # Generate bars at 1-minute intervals
        while current_time <= request.end_date:
            # Random walk
            change = np.random.normal(0, 0.001)
            open_price = price
            high_price = price * (1 + np.random.uniform(0, 0.005))
            low_price = price * (1 - np.random.uniform(0, 0.005))
            close_price = price * (1 + change)
            price = close_price
            
            bars.append(ReplayBar(
                timestamp=current_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=np.random.uniform(1000, 10000),
                trades=int(np.random.uniform(10, 100)),
                bid=close_price * 0.999,
                ask=close_price * 1.001
            ))
            
            current_time += timedelta(minutes=1)
        
        return bars

    # =========================================================================
    # Replay Execution
    # =========================================================================

    async def _start_replay_loop(self, replay_id: str) -> None:
        """Start replay loop"""
        if replay_id not in self._replays:
            return
        
        state = self._replays[replay_id]
        state.status = ReplayStatus.RUNNING
        self._replays[replay_id] = state
        
        # Start monitoring if not running
        if not self._is_running:
            await self._start_monitoring()

    async def _replay_loop(self, replay_id: str) -> None:
        """Main replay loop"""
        if replay_id not in self._replays:
            return
        
        state = self._replays[replay_id]
        
        while state.status == ReplayStatus.RUNNING:
            if state.processed_bars >= state.total_bars:
                state.status = ReplayStatus.COMPLETED
                self._replays[replay_id] = state
                break
            
            # Get next bar
            bar = state.bars[state.processed_bars]
            state.current_date = bar.timestamp
            
            # Process bar
            await self._process_bar(state, bar)
            
            # Update state
            state.processed_bars += 1
            state.updated_at = datetime.utcnow()
            self._replays[replay_id] = state
            
            # Calculate sleep time based on speed
            sleep_time = self._calculate_sleep_time(state.speed)
            await asyncio.sleep(sleep_time)

    async def _process_bar(self, state: ReplayState, bar: ReplayBar) -> None:
        """Process a single bar"""
        try:
            # Update market price
            await self._update_market_price(state.symbol, bar)
            
            # Update portfolio
            await self._update_portfolio(state, bar)
            
            # Execute pending orders
            await self._execute_orders(state, bar)
            
        except Exception as e:
            logger.error(f"Error processing bar: {e}")

    async def _update_market_price(self, symbol: str, bar: ReplayBar) -> None:
        """Update market price"""
        # Update paper market price
        # This would call paper_market.update_price()
        pass

    async def _update_portfolio(self, state: ReplayState, bar: ReplayBar) -> None:
        """Update portfolio"""
        # Calculate PnL
        portfolio = await self.paper_portfolio.get_portfolio(state.account_id)
        if portfolio:
            state.equity = portfolio.total_value
            state.pnl = portfolio.total_pnl

    async def _execute_orders(self, state: ReplayState, bar: ReplayBar) -> None:
        """Execute pending orders"""
        # Check and execute orders
        # This would call paper_orders.check_orders()
        pass

    def _calculate_sleep_time(self, speed: ReplaySpeed) -> float:
        """Calculate sleep time between bars"""
        base_time = 1.0  # 1 second per bar at real-time
        
        speed_map = {
            ReplaySpeed.REAL_TIME: 1.0,
            ReplaySpeed.FAST: 0.5,
            ReplaySpeed.VERY_FAST: 0.2,
            ReplaySpeed.ULTRA_FAST: 0.1,
            ReplaySpeed.MAX: 0.001
        }
        
        multiplier = speed_map.get(speed, 1.0)
        return base_time * multiplier

    # =========================================================================
    # Replay Control
    # =========================================================================

    async def pause_replay(self, replay_id: str) -> ReplayResponse:
        """
        Pause a replay.
        
        Args:
            replay_id: Replay ID
            
        Returns:
            ReplayResponse: Replay status
        """
        if replay_id not in self._replays:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay {replay_id} not found"
            )
        
        state = self._replays[replay_id]
        state.status = ReplayStatus.PAUSED
        self._replays[replay_id] = state
        
        logger.info(f"Replay {replay_id} paused")
        return self._to_response(replay_id)

    async def resume_replay(self, replay_id: str) -> ReplayResponse:
        """
        Resume a replay.
        
        Args:
            replay_id: Replay ID
            
        Returns:
            ReplayResponse: Replay status
        """
        if replay_id not in self._replays:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay {replay_id} not found"
            )
        
        state = self._replays[replay_id]
        state.status = ReplayStatus.RUNNING
        self._replays[replay_id] = state
        
        logger.info(f"Replay {replay_id} resumed")
        return self._to_response(replay_id)

    async def stop_replay(self, replay_id: str) -> ReplayResponse:
        """
        Stop a replay.
        
        Args:
            replay_id: Replay ID
            
        Returns:
            ReplayResponse: Replay status
        """
        if replay_id not in self._replays:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay {replay_id} not found"
            )
        
        state = self._replays[replay_id]
        state.status = ReplayStatus.STOPPED
        self._replays[replay_id] = state
        
        logger.info(f"Replay {replay_id} stopped")
        return self._to_response(replay_id)

    async def set_speed(
        self,
        replay_id: str,
        speed: ReplaySpeed
    ) -> ReplayResponse:
        """
        Set replay speed.
        
        Args:
            replay_id: Replay ID
            speed: New speed
            
        Returns:
            ReplayResponse: Replay status
        """
        if replay_id not in self._replays:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay {replay_id} not found"
            )
        
        state = self._replays[replay_id]
        state.speed = speed
        self._replays[replay_id] = state
        
        logger.info(f"Replay {replay_id} speed set to {speed.value}")
        return self._to_response(replay_id)

    async def get_replay(self, replay_id: str) -> ReplayResponse:
        """
        Get replay status.
        
        Args:
            replay_id: Replay ID
            
        Returns:
            ReplayResponse: Replay status
        """
        if replay_id not in self._replays:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay {replay_id} not found"
            )
        
        return self._to_response(replay_id)

    def _to_response(self, replay_id: str) -> ReplayResponse:
        """Convert replay to response"""
        state = self._replays[replay_id]
        
        return ReplayResponse(
            replay_id=replay_id,
            account_id=state.account_id,
            symbol=state.symbol,
            status=state.status,
            speed=state.speed,
            start_date=state.start_date,
            end_date=state.end_date,
            current_date=state.current_date,
            progress=(state.processed_bars / state.total_bars * 100) if state.total_bars > 0 else 0,
            total_bars=state.total_bars,
            processed_bars=state.processed_bars,
            trades_executed=state.trades_executed,
            pnl=state.pnl,
            started_at=state.started_at,
            updated_at=state.updated_at,
            metadata=self._replay_info.get(replay_id, {}).get('metadata', {})
        )

    # =========================================================================
    # Replay Summary
    # =========================================================================

    async def get_summary(self, replay_id: str) -> ReplaySummaryResponse:
        """
        Get replay summary.
        
        Args:
            replay_id: Replay ID
            
        Returns:
            ReplaySummaryResponse: Replay summary
        """
        if replay_id not in self._replays:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay {replay_id} not found"
            )
        
        state = self._replays[replay_id]
        
        # Calculate metrics
        trades = await self._get_replay_trades(replay_id)
        
        win_rate = 0
        profit_factor = 0
        max_drawdown = 0
        
        if trades:
            wins = [t for t in trades if t.get('pnl', 0) > 0]
            losses = [t for t in trades if t.get('pnl', 0) < 0]
            
            win_rate = len(wins) / len(trades) if trades else 0
            
            gross_profit = sum(t.get('pnl', 0) for t in wins)
            gross_loss = abs(sum(t.get('pnl', 0) for t in losses))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Calculate drawdown
            equity = [state.equity]
            for trade in trades:
                equity.append(equity[-1] + trade.get('pnl', 0))
            
            peak = max(equity)
            max_drawdown = (peak - equity[-1]) / peak if peak > 0 else 0
        
        return ReplaySummaryResponse(
            replay_id=replay_id,
            symbol=state.symbol,
            start_date=state.start_date,
            end_date=state.end_date,
            total_bars=state.total_bars,
            processed_bars=state.processed_bars,
            execution_time=(state.updated_at - state.started_at).total_seconds(),
            trades_executed=state.trades_executed,
            final_pnl=state.pnl,
            final_equity=state.equity,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            summary={
                'status': state.status.value,
                'progress': (state.processed_bars / state.total_bars * 100) if state.total_bars > 0 else 0
            },
            metadata=self._replay_info.get(replay_id, {}).get('metadata', {})
        )

    async def _get_replay_trades(self, replay_id: str) -> List[Dict[str, Any]]:
        """Get trades from replay"""
        # This would fetch trades from the database
        return []

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def _start_monitoring(self) -> None:
        """Start monitoring"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Replay monitoring started")

    async def _stop_monitoring(self) -> None:
        """Stop monitoring"""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Replay monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_running:
            try:
                # Run active replays
                for replay_id, state in list(self._replays.items()):
                    if state.status == ReplayStatus.RUNNING:
                        await self._replay_loop(replay_id)
                
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(1)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the replay module"""
        await self._stop_monitoring()
        
        # Stop all replays
        for replay_id in list(self._replays.keys()):
            try:
                await self.stop_replay(replay_id)
            except Exception as e:
                logger.error(f"Error stopping replay {replay_id}: {e}")
        
        self._replays.clear()
        self._replay_info.clear()
        self._data_cache.clear()
        
        logger.info("PaperTradingReplay closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/replay", tags=["Paper Trading Replay"])


async def get_replay() -> PaperTradingReplay:
    """Dependency to get PaperTradingReplay instance"""
    return PaperTradingReplay()


@router.post("/start", response_model=ReplayResponse)
async def start_replay(
    request: ReplayRequest,
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Start a replay"""
    return await replay.start_replay(request)


@router.post("/{replay_id}/pause")
async def pause_replay(
    replay_id: str,
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Pause a replay"""
    return await replay.pause_replay(replay_id)


@router.post("/{replay_id}/resume")
async def resume_replay(
    replay_id: str,
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Resume a replay"""
    return await replay.resume_replay(replay_id)


@router.post("/{replay_id}/stop")
async def stop_replay(
    replay_id: str,
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Stop a replay"""
    return await replay.stop_replay(replay_id)


@router.put("/{replay_id}/speed")
async def set_replay_speed(
    replay_id: str,
    speed: ReplaySpeed = Body(..., embed=True),
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Set replay speed"""
    return await replay.set_speed(replay_id, speed)


@router.get("/{replay_id}")
async def get_replay(
    replay_id: str,
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Get replay status"""
    return await replay.get_replay(replay_id)


@router.get("/{replay_id}/summary")
async def get_replay_summary(
    replay_id: str,
    replay: PaperTradingReplay = Depends(get_replay)
):
    """Get replay summary"""
    return await replay.get_summary(replay_id)


@router.get("/speeds")
async def get_replay_speeds():
    """Get available replay speeds"""
    return {
        'speeds': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in ReplaySpeed
        ]
    }


@router.get("/data-sources")
async def get_data_sources():
    """Get available data sources"""
    return {
        'sources': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in DataSource
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingReplay',
    'ReplayStatus',
    'ReplaySpeed',
    'DataSource',
    'ReplayRequest',
    'ReplayResponse',
    'ReplayBarData',
    'ReplaySummaryResponse',
    'ReplayState',
    'ReplayBar',
    'router'
]

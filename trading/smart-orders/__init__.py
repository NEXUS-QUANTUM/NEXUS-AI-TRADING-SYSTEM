"""
NEXUS AI TRADING SYSTEM - Smart Orders Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/__init__.py
Version: 1.0.0
Description: Smart orders module initialization and exports
"""

from trading.smart_orders.base_order import (
    SmartOrder,
    SmartOrderConfig,
    SmartOrderState,
    OrderFill
)

from trading.smart_orders.trailing_stop import (
    TrailingStop,
    TrailingStopConfig,
    TrailingStopType,
    TrailingStopMode,
    TrailingStopState,
    TrailingStopMetrics,
    TrailingStopExecution
)

from trading.smart_orders.smart_take_profit import (
    SmartTakeProfit,
    SmartTakeProfitConfig,
    TakeProfitType,
    TakeProfitMode,
    TakeProfitDistribution,
    TakeProfitLevel,
    TakeProfitMetrics,
    TakeProfitExecution
)

from trading.smart_orders.smart_stop import (
    SmartStop,
    SmartStopConfig,
    SmartStopType,
    SmartStopMode,
    SmartStopLevel,
    SmartStopMetrics,
    StopExecution
)

from trading.smart_orders.scaling_order import (
    ScalingOrder,
    ScalingOrderConfig,
    ScalingType,
    ScalingDirection,
    ScalingMode,
    ScalingLevel,
    ScalingMetrics,
    LevelExecution
)

from trading.smart_orders.order_manager import (
    OrderManager,
    OrderTypeCategory,
    OrderPriority,
    OrderFilter,
    OrderSummary,
    OrderEvent
)

from trading.smart_orders.order_executor import (
    OrderExecutor,
    ExecutionConfig,
    ExecutionType,
    ExecutionPriority,
    ExecutionMode,
    ExecutionResult,
    ExecutionMetrics
)

from trading.smart_orders.oco_order import (
    OCOOrder,
    OCOConfig,
    OCOType,
    OCOLegType,
    OCOLeg,
    OCOState,
    OCOExecution,
    OCOMetrics
)

from trading.smart_orders.iceberg import (
    IcebergOrder,
    IcebergConfig,
    IcebergRefreshMode,
    IcebergSizeMode,
    IcebergPricing,
    IcebergPiece,
    IcebergMetrics
)

from trading.smart_orders.conditional_order import (
    ConditionalOrder,
    ConditionalOrderConfig,
    ConditionType,
    ComparisonOperator,
    LogicalOperator,
    IndicatorType,
    TimeCondition,
    Condition,
    CompoundCondition,
    ConditionalActionType,
    ConditionalAction,
    ConditionalState,
    ConditionHistory,
    ConditionalMetrics
)

from trading.smart_orders.bracket_order import (
    BracketOrder,
    BracketOrderConfig,
    BracketType,
    BracketStatus,
    BracketLeg,
    BracketMetrics
)

__all__ = [
    # Base
    'SmartOrder',
    'SmartOrderConfig',
    'SmartOrderState',
    'OrderFill',
    
    # Trailing Stop
    'TrailingStop',
    'TrailingStopConfig',
    'TrailingStopType',
    'TrailingStopMode',
    'TrailingStopState',
    'TrailingStopMetrics',
    'TrailingStopExecution',
    
    # Smart Take Profit
    'SmartTakeProfit',
    'SmartTakeProfitConfig',
    'TakeProfitType',
    'TakeProfitMode',
    'TakeProfitDistribution',
    'TakeProfitLevel',
    'TakeProfitMetrics',
    'TakeProfitExecution',
    
    # Smart Stop
    'SmartStop',
    'SmartStopConfig',
    'SmartStopType',
    'SmartStopMode',
    'SmartStopLevel',
    'SmartStopMetrics',
    'StopExecution',
    
    # Scaling Order
    'ScalingOrder',
    'ScalingOrderConfig',
    'ScalingType',
    'ScalingDirection',
    'ScalingMode',
    'ScalingLevel',
    'ScalingMetrics',
    'LevelExecution',
    
    # Order Manager
    'OrderManager',
    'OrderTypeCategory',
    'OrderPriority',
    'OrderFilter',
    'OrderSummary',
    'OrderEvent',
    
    # Order Executor
    'OrderExecutor',
    'ExecutionConfig',
    'ExecutionType',
    'ExecutionPriority',
    'ExecutionMode',
    'ExecutionResult',
    'ExecutionMetrics',
    
    # OCO Order
    'OCOOrder',
    'OCOConfig',
    'OCOType',
    'OCOLegType',
    'OCOLeg',
    'OCOState',
    'OCOExecution',
    'OCOMetrics',
    
    # Iceberg
    'IcebergOrder',
    'IcebergConfig',
    'IcebergRefreshMode',
    'IcebergSizeMode',
    'IcebergPricing',
    'IcebergPiece',
    'IcebergMetrics',
    
    # Conditional Order
    'ConditionalOrder',
    'ConditionalOrderConfig',
    'ConditionType',
    'ComparisonOperator',
    'LogicalOperator',
    'IndicatorType',
    'TimeCondition',
    'Condition',
    'CompoundCondition',
    'ConditionalActionType',
    'ConditionalAction',
    'ConditionalState',
    'ConditionHistory',
    'ConditionalMetrics',
    
    # Bracket Order
    'BracketOrder',
    'BracketOrderConfig',
    'BracketType',
    'BracketStatus',
    'BracketLeg',
    'BracketMetrics',
]


# Module metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module description
MODULE_DESCRIPTION = """
NEXUS Smart Orders Module

This module provides advanced smart order types for algorithmic trading:

1. TrailingStop - Advanced trailing stop with multiple modes
2. SmartTakeProfit - Smart take profit with multiple levels
3. SmartStop - Smart stop loss with adaptive features
4. ScalingOrder - Scaling orders with multiple strategies
5. OCOOrder - One-Cancels-Other orders
6. IcebergOrder - Iceberg orders with hidden size
7. ConditionalOrder - Condition-based order execution
8. BracketOrder - Bracket orders with take profit and stop loss

Features:
- Full API integration
- Event-driven architecture
- Performance metrics
- Risk management
- Error handling
- State persistence
"""


def get_module_info() -> Dict[str, Any]:
    """
    Get module information.

    Returns:
        Dict[str, Any]: Module information
    """
    return {
        'name': 'smart_orders',
        'version': __version__,
        'author': __author__,
        'copyright': __copyright__,
        'description': MODULE_DESCRIPTION,
        'exports': __all__,
        'classes': [
            cls_name for cls_name in __all__ 
            if cls_name[0].isupper() and not cls_name.endswith('Config')
        ],
        'configs': [
            cls_name for cls_name in __all__ 
            if cls_name.endswith('Config')
        ],
        'enums': [
            cls_name for cls_name in __all__ 
            if cls_name[0].isupper() and cls_name.endswith(('Type', 'Mode', 'State', 'Status', 'Priority', 'Direction', 'Distribution', 'Pricing', 'RefreshMode', 'SizeMode', 'LegType', 'Operator', 'Indicator'))
        ]
    }


# Lazy imports for heavy dependencies
def lazy_import(module_name: str):
    """
    Lazy import a module.
    
    Args:
        module_name: Name of the module to import
    
    Returns:
        Module: Imported module
    """
    import importlib
    return importlib.import_module(f"trading.smart_orders.{module_name}")


# Convenience factory functions
def create_trailing_stop(
    symbol: str,
    side: str,
    quantity: float,
    trailing_percent: float = 1.0,
    activation_percent: float = 0.5,
    mode: str = "standard",
    **kwargs
) -> TrailingStop:
    """
    Create a trailing stop order.
    
    Args:
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        quantity: Order quantity
        trailing_percent: Trailing percentage
        activation_percent: Activation percentage
        mode: Trailing mode
        **kwargs: Additional configuration parameters
    
    Returns:
        TrailingStop: Trailing stop instance
    """
    config = TrailingStopConfig(
        symbol=symbol,
        side=OrderSide(side.upper()),
        order_size=quantity,
        trailing_percent=trailing_percent,
        activation_percent=activation_percent,
        mode=TrailingStopMode(mode.lower()),
        **kwargs
    )
    return TrailingStop(config=config)


def create_smart_take_profit(
    symbol: str,
    side: str,
    quantity: float,
    target_percent: float = 2.0,
    mode: str = "single",
    levels: int = 3,
    **kwargs
) -> SmartTakeProfit:
    """
    Create a smart take profit order.
    
    Args:
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        quantity: Order quantity
        target_percent: Target percentage
        mode: Take profit mode
        levels: Number of levels for multi-mode
        **kwargs: Additional configuration parameters
    
    Returns:
        SmartTakeProfit: Smart take profit instance
    """
    config = SmartTakeProfitConfig(
        symbol=symbol,
        side=OrderSide(side.upper()),
        order_size=quantity,
        target_percent=target_percent,
        mode=TakeProfitMode(mode.lower()),
        number_of_levels=levels,
        **kwargs
    )
    return SmartTakeProfit(config=config)


def create_smart_stop(
    symbol: str,
    side: str,
    quantity: float,
    stop_percent: float = 1.0,
    mode: str = "standard",
    **kwargs
) -> SmartStop:
    """
    Create a smart stop order.
    
    Args:
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        quantity: Order quantity
        stop_percent: Stop loss percentage
        mode: Stop mode
        **kwargs: Additional configuration parameters
    
    Returns:
        SmartStop: Smart stop instance
    """
    config = SmartStopConfig(
        symbol=symbol,
        side=OrderSide(side.upper()),
        order_size=quantity,
        stop_percent=stop_percent,
        mode=SmartStopMode(mode.lower()),
        **kwargs
    )
    return SmartStop(config=config)


def create_scaling_order(
    symbol: str,
    side: str,
    total_size: float,
    start_price: float,
    levels: int = 5,
    scaling_type: str = "fixed",
    mode: str = "linear",
    **kwargs
) -> ScalingOrder:
    """
    Create a scaling order.
    
    Args:
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        total_size: Total order size
        start_price: Starting price
        levels: Number of scaling levels
        scaling_type: Scaling type
        mode: Scaling mode
        **kwargs: Additional configuration parameters
    
    Returns:
        ScalingOrder: Scaling order instance
    """
    config = ScalingOrderConfig(
        symbol=symbol,
        side=OrderSide(side.upper()),
        total_size=total_size,
        start_price=start_price,
        number_of_levels=levels,
        scaling_type=ScalingType(scaling_type.lower()),
        mode=ScalingMode(mode.lower()),
        **kwargs
    )
    return ScalingOrder(config=config)


def create_oco_order(
    symbol: str,
    side: str,
    total_size: float,
    entry_price: float,
    take_profit_price: float,
    stop_loss_price: float,
    oco_type: str = "standard",
    **kwargs
) -> OCOOrder:
    """
    Create an OCO order.
    
    Args:
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        total_size: Total order size
        entry_price: Entry price
        take_profit_price: Take profit price
        stop_loss_price: Stop loss price
        oco_type: OCO type
        **kwargs: Additional configuration parameters
    
    Returns:
        OCOOrder: OCO order instance
    """
    config = OCOConfig(
        symbol=symbol,
        side=OrderSide(side.upper()),
        total_size=total_size,
        entry_price=entry_price,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        oco_type=OCOType(oco_type.lower()),
        **kwargs
    )
    return OCOOrder(config=config)


def create_bracket_order(
    symbol: str,
    side: str,
    entry_size: float,
    entry_price: float,
    take_profit_percent: float = 2.0,
    stop_loss_percent: float = 1.0,
    bracket_type: str = "standard",
    **kwargs
) -> BracketOrder:
    """
    Create a bracket order.
    
    Args:
        symbol: Trading symbol
        side: Order side (BUY/SELL)
        entry_size: Entry size
        entry_price: Entry price
        take_profit_percent: Take profit percentage
        stop_loss_percent: Stop loss percentage
        bracket_type: Bracket type
        **kwargs: Additional configuration parameters
    
    Returns:
        BracketOrder: Bracket order instance
    """
    config = BracketOrderConfig(
        symbol=symbol,
        side=OrderSide(side.upper()),
        entry_size=entry_size,
        entry_price=entry_price,
        take_profit_percent=take_profit_percent,
        stop_loss_percent=stop_loss_percent,
        bracket_type=BracketType(bracket_type.lower()),
        **kwargs
    )
    return BracketOrder(config=config)


# Version check
def get_version() -> str:
    """Get module version."""
    return __version__


# Export everything
__all__ = sorted(__all__)

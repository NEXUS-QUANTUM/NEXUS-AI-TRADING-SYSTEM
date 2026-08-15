"""
Swing Bot Validators Module
============================

This module provides validation utilities for the Swing Bot trading system.
Includes validators for data, configurations, orders, risk parameters, and market data.
"""

import re
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import numbers


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class Validator:
    """Base validator class for Swing Bot."""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.errors: List[str] = []
    
    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """Validate data and return (is_valid, errors)."""
        raise NotImplementedError("Subclasses must implement validate()")
    
    def add_error(self, error: str) -> None:
        """Add an error to the errors list."""
        self.errors.append(error)
    
    def clear_errors(self) -> None:
        """Clear all errors."""
        self.errors.clear()
    
    def is_valid(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) == 0


class DataValidator(Validator):
    """Validator for trading data."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.required_fields = ['symbol', 'price', 'volume', 'timestamp']
        self.price_min = 0.0001
        self.volume_min = 0.0
        self.max_price_change_pct = 50.0
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate trading data dictionary."""
        self.clear_errors()
        
        if not data or not isinstance(data, dict):
            self.add_error("Data must be a non-empty dictionary")
            return False, self.errors
        
        # Validate required fields
        for field in self.required_fields:
            if field not in data:
                self.add_error(f"Missing required field: {field}")
        
        # Validate symbol
        if 'symbol' in data:
            symbol = data['symbol']
            if not isinstance(symbol, str) or not symbol:
                self.add_error("Symbol must be a non-empty string")
            elif not re.match(r'^[A-Z0-9/_.-]+$', symbol):
                self.add_error(f"Invalid symbol format: {symbol}")
        
        # Validate price
        if 'price' in data:
            price = data['price']
            if not isinstance(price, numbers.Number):
                self.add_error("Price must be a number")
            elif price < self.price_min:
                self.add_error(f"Price must be at least {self.price_min}")
            elif price > 1e9:
                self.add_error("Price exceeds maximum allowed value")
        
        # Validate volume
        if 'volume' in data:
            volume = data['volume']
            if not isinstance(volume, numbers.Number):
                self.add_error("Volume must be a number")
            elif volume < self.volume_min:
                self.add_error(f"Volume must be at least {self.volume_min}")
        
        # Validate timestamp
        if 'timestamp' in data:
            timestamp = data['timestamp']
            if not isinstance(timestamp, (int, float, str, datetime)):
                self.add_error("Timestamp must be int, float, str, or datetime")
            elif isinstance(timestamp, (int, float)) and timestamp < 0:
                self.add_error("Timestamp cannot be negative")
            elif isinstance(timestamp, datetime):
                if timestamp > datetime.now() + timedelta(days=1):
                    self.add_error("Timestamp cannot be in the future")
        
        return self.is_valid(), self.errors


class OrderValidator(Validator):
    """Validator for trading orders."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.order_types = ['market', 'limit', 'stop', 'stop_limit', 'trailing_stop', 'iceberg', 'twap', 'vwap']
        self.time_in_force = ['day', 'gtc', 'ioc', 'fok', 'gtx', 'gtd']
        self.order_sides = ['buy', 'sell', 'short', 'cover']
    
    def validate(self, order: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate order data."""
        self.clear_errors()
        
        if not order or not isinstance(order, dict):
            self.add_error("Order must be a non-empty dictionary")
            return False, self.errors
        
        # Validate symbol
        if 'symbol' not in order:
            self.add_error("Missing required field: symbol")
        elif not isinstance(order['symbol'], str) or not order['symbol']:
            self.add_error("Symbol must be a non-empty string")
        
        # Validate side
        if 'side' not in order:
            self.add_error("Missing required field: side")
        elif order['side'] not in self.order_sides:
            self.add_error(f"Invalid side: {order['side']}. Must be one of {self.order_sides}")
        
        # Validate order type
        if 'order_type' not in order:
            self.add_error("Missing required field: order_type")
        elif order['order_type'] not in self.order_types:
            self.add_error(f"Invalid order_type: {order['order_type']}. Must be one of {self.order_types}")
        
        # Validate quantity
        if 'quantity' not in order:
            self.add_error("Missing required field: quantity")
        else:
            qty = order['quantity']
            if not isinstance(qty, numbers.Number) or qty <= 0:
                self.add_error("Quantity must be a positive number")
        
        # Validate price (for limit/stop orders)
        order_type = order.get('order_type', '')
        if order_type in ['limit', 'stop_limit']:
            if 'price' not in order:
                self.add_error(f"{order_type} orders require price")
            elif not isinstance(order['price'], numbers.Number) or order['price'] <= 0:
                self.add_error("Price must be a positive number")
        
        # Validate stop price (for stop/stop_limit orders)
        if order_type in ['stop', 'stop_limit']:
            if 'stop_price' not in order:
                self.add_error(f"{order_type} orders require stop_price")
            elif not isinstance(order['stop_price'], numbers.Number) or order['stop_price'] <= 0:
                self.add_error("Stop price must be a positive number")
        
        # Validate time in force
        if 'time_in_force' in order:
            tif = order['time_in_force']
            if tif not in self.time_in_force:
                self.add_error(f"Invalid time_in_force: {tif}. Must be one of {self.time_in_force}")
        
        return self.is_valid(), self.errors


class RiskValidator(Validator):
    """Validator for risk parameters."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.max_position_size = 0.25
        self.max_leverage = 10.0
        self.max_var = 0.05
        self.max_drawdown = 0.15
        self.min_sharpe = 0.0
    
    def validate(self, risk_params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate risk parameters."""
        self.clear_errors()
        
        if not risk_params or not isinstance(risk_params, dict):
            self.add_error("Risk parameters must be a non-empty dictionary")
            return False, self.errors
        
        # Validate position size
        if 'position_size' in risk_params:
            size = risk_params['position_size']
            if not isinstance(size, numbers.Number) or size < 0:
                self.add_error("Position size must be a non-negative number")
            elif size > self.max_position_size:
                self.add_error(f"Position size ({size}) exceeds maximum {self.max_position_size}")
        
        # Validate leverage
        if 'leverage' in risk_params:
            leverage = risk_params['leverage']
            if not isinstance(leverage, numbers.Number) or leverage < 0:
                self.add_error("Leverage must be a non-negative number")
            elif leverage > self.max_leverage:
                self.add_error(f"Leverage ({leverage}) exceeds maximum {self.max_leverage}")
        
        # Validate VaR
        if 'value_at_risk' in risk_params:
            var = risk_params['value_at_risk']
            if not isinstance(var, numbers.Number) or var < 0:
                self.add_error("VaR must be a non-negative number")
            elif var > self.max_var:
                self.add_error(f"VaR ({var}) exceeds maximum {self.max_var}")
        
        # Validate drawdown
        if 'max_drawdown' in risk_params:
            drawdown = risk_params['max_drawdown']
            if not isinstance(drawdown, numbers.Number) or drawdown < 0:
                self.add_error("Max drawdown must be a non-negative number")
            elif drawdown > self.max_drawdown:
                self.add_error(f"Max drawdown ({drawdown}) exceeds maximum {self.max_drawdown}")
        
        # Validate Sharpe ratio
        if 'sharpe_ratio' in risk_params:
            sharpe = risk_params['sharpe_ratio']
            if not isinstance(sharpe, numbers.Number):
                self.add_error("Sharpe ratio must be a number")
            elif sharpe < self.min_sharpe:
                self.add_error(f"Sharpe ratio ({sharpe}) is below minimum {self.min_sharpe}")
        
        return self.is_valid(), self.errors


class ConfigValidator(Validator):
    """Validator for configuration files."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.required_config_keys = ['enabled', 'version']
        self.config_types = {
            'enabled': bool,
            'version': str,
            'analysis_mode': str,
            'update_frequency_seconds': int,
            'lookback_period': int,
            'threshold': numbers.Number,
        }
    
    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate configuration dictionary."""
        self.clear_errors()
        
        if not config or not isinstance(config, dict):
            self.add_error("Configuration must be a non-empty dictionary")
            return False, self.errors
        
        # Check required keys
        for key in self.required_config_keys:
            if key not in config:
                self.add_error(f"Missing required config key: {key}")
        
        # Validate types
        for key, expected_type in self.config_types.items():
            if key in config:
                value = config[key]
                if not isinstance(value, expected_type):
                    # Special case for numbers
                    if expected_type == numbers.Number and isinstance(value, numbers.Number):
                        continue
                    self.add_error(f"Config key '{key}' must be of type {expected_type.__name__}")
        
        # Validate nested structures
        for key, value in config.items():
            if isinstance(value, dict):
                sub_validator = ConfigValidator(self.strict_mode)
                sub_validator.validate(value)
                self.errors.extend(sub_validator.errors)
        
        return self.is_valid(), self.errors


class MarketDataValidator(Validator):
    """Validator for market data."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.required_fields = ['symbol', 'bid', 'ask', 'last', 'volume', 'timestamp']
        self.min_spread = 0.0
        self.max_spread_ratio = 0.10
    
    def validate(self, market_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate market data."""
        self.clear_errors()
        
        if not market_data or not isinstance(market_data, dict):
            self.add_error("Market data must be a non-empty dictionary")
            return False, self.errors
        
        # Validate required fields
        for field in self.required_fields:
            if field not in market_data:
                self.add_error(f"Missing required field: {field}")
        
        # Validate symbol
        if 'symbol' in market_data:
            symbol = market_data['symbol']
            if not isinstance(symbol, str) or not symbol:
                self.add_error("Symbol must be a non-empty string")
        
        # Validate prices
        for price_field in ['bid', 'ask', 'last']:
            if price_field in market_data:
                price = market_data[price_field]
                if not isinstance(price, numbers.Number) or price <= 0:
                    self.add_error(f"{price_field} must be a positive number")
        
        # Validate spread
        if 'bid' in market_data and 'ask' in market_data:
            bid = market_data['bid']
            ask = market_data['ask']
            if ask < bid:
                self.add_error("Ask price must be greater than or equal to bid price")
            elif bid > 0:
                spread_ratio = (ask - bid) / bid
                if spread_ratio > self.max_spread_ratio:
                    self.add_error(f"Spread ratio ({spread_ratio:.2%}) exceeds maximum {self.max_spread_ratio:.2%}")
        
        # Validate volume
        if 'volume' in market_data:
            volume = market_data['volume']
            if not isinstance(volume, numbers.Number) or volume < 0:
                self.add_error("Volume must be a non-negative number")
        
        return self.is_valid(), self.errors


class TimeValidator(Validator):
    """Validator for time-related data."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.time_formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
        ]
    
    def validate(self, time_data: Any) -> Tuple[bool, List[str]]:
        """Validate time data."""
        self.clear_errors()
        
        if time_data is None:
            self.add_error("Time data cannot be None")
            return False, self.errors
        
        # Check if it's a datetime object
        if isinstance(time_data, datetime):
            return True, []
        
        # Check if it's a timestamp (int or float)
        if isinstance(time_data, (int, float)):
            if time_data < 0:
                self.add_error("Timestamp cannot be negative")
            elif time_data > 10**13:  # Check for milliseconds vs seconds
                try:
                    datetime.fromtimestamp(time_data / 1000)
                except (ValueError, OSError):
                    self.add_error(f"Invalid timestamp: {time_data}")
            else:
                try:
                    datetime.fromtimestamp(time_data)
                except (ValueError, OSError):
                    self.add_error(f"Invalid timestamp: {time_data}")
            return self.is_valid(), self.errors
        
        # Check if it's a string
        if isinstance(time_data, str):
            for fmt in self.time_formats:
                try:
                    datetime.strptime(time_data, fmt)
                    return True, []
                except ValueError:
                    continue
            self.add_error(f"Invalid time string format: {time_data}")
            return False, self.errors
        
        self.add_error(f"Time data must be datetime, timestamp, or string, got {type(time_data)}")
        return False, self.errors


class SymbolValidator(Validator):
    """Validator for trading symbols."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.symbol_pattern = re.compile(r'^[A-Z0-9/_.-]+$')
        self.min_length = 1
        self.max_length = 20
    
    def validate(self, symbol: Any) -> Tuple[bool, List[str]]:
        """Validate a trading symbol."""
        self.clear_errors()
        
        if symbol is None:
            self.add_error("Symbol cannot be None")
            return False, self.errors
        
        if not isinstance(symbol, str):
            self.add_error(f"Symbol must be a string, got {type(symbol)}")
            return False, self.errors
        
        if not symbol:
            self.add_error("Symbol cannot be empty")
            return False, self.errors
        
        if len(symbol) < self.min_length:
            self.add_error(f"Symbol length {len(symbol)} is less than minimum {self.min_length}")
        
        if len(symbol) > self.max_length:
            self.add_error(f"Symbol length {len(symbol)} exceeds maximum {self.max_length}")
        
        if not self.symbol_pattern.match(symbol):
            self.add_error(f"Symbol contains invalid characters: {symbol}")
        
        return self.is_valid(), self.errors


class PositionValidator(Validator):
    """Validator for trading positions."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.position_types = ['long', 'short', 'flat']
    
    def validate(self, position: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate position data."""
        self.clear_errors()
        
        if not position or not isinstance(position, dict):
            self.add_error("Position must be a non-empty dictionary")
            return False, self.errors
        
        # Validate symbol
        if 'symbol' not in position:
            self.add_error("Missing required field: symbol")
        else:
            symbol_validator = SymbolValidator()
            symbol_validator.validate(position['symbol'])
            self.errors.extend(symbol_validator.errors)
        
        # Validate position type
        if 'position_type' in position:
            pos_type = position['position_type']
            if pos_type not in self.position_types:
                self.add_error(f"Invalid position_type: {pos_type}. Must be one of {self.position_types}")
        
        # Validate quantity
        if 'quantity' not in position:
            self.add_error("Missing required field: quantity")
        else:
            qty = position['quantity']
            if not isinstance(qty, numbers.Number):
                self.add_error("Quantity must be a number")
            elif qty < 0:
                self.add_error("Quantity cannot be negative")
        
        # Validate entry price
        if 'entry_price' in position:
            price = position['entry_price']
            if not isinstance(price, numbers.Number) or price <= 0:
                self.add_error("Entry price must be a positive number")
        
        # Validate current price
        if 'current_price' in position:
            price = position['current_price']
            if not isinstance(price, numbers.Number) or price <= 0:
                self.add_error("Current price must be a positive number")
        
        return self.is_valid(), self.errors


class PortfolioValidator(Validator):
    """Validator for portfolio data."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.max_positions = 50
        self.max_allocation_per_asset = 0.25
        self.max_sector_concentration = 0.40
    
    def validate(self, portfolio: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate portfolio data."""
        self.clear_errors()
        
        if not portfolio or not isinstance(portfolio, dict):
            self.add_error("Portfolio must be a non-empty dictionary")
            return False, self.errors
        
        # Validate positions
        if 'positions' not in portfolio:
            self.add_error("Missing required field: positions")
        else:
            positions = portfolio['positions']
            if not isinstance(positions, list):
                self.add_error("Positions must be a list")
            else:
                if len(positions) > self.max_positions:
                    self.add_error(f"Number of positions ({len(positions)}) exceeds maximum {self.max_positions}")
                
                # Validate each position
                position_validator = PositionValidator()
                for i, position in enumerate(positions):
                    position_validator.validate(position)
                    self.errors.extend([f"Position {i}: {e}" for e in position_validator.errors])
        
        # Validate total value
        if 'total_value' in portfolio:
            total = portfolio['total_value']
            if not isinstance(total, numbers.Number) or total < 0:
                self.add_error("Total value must be a non-negative number")
        
        # Validate allocation
        if 'allocation' in portfolio:
            allocation = portfolio['allocation']
            if not isinstance(allocation, dict):
                self.add_error("Allocation must be a dictionary")
            else:
                for asset, weight in allocation.items():
                    if not isinstance(weight, numbers.Number) or weight < 0:
                        self.add_error(f"Allocation weight for {asset} must be a non-negative number")
                    elif weight > self.max_allocation_per_asset:
                        self.add_error(f"Allocation weight for {asset} ({weight}) exceeds maximum {self.max_allocation_per_asset}")
        
        return self.is_valid(), self.errors


class TradeValidator(Validator):
    """Validator for trade data."""
    
    def __init__(self, strict_mode: bool = True):
        super().__init__(strict_mode)
        self.trade_types = ['market', 'limit', 'stop', 'stop_limit', 'trailing_stop']
        self.trade_statuses = ['pending', 'open', 'filled', 'partially_filled', 'cancelled', 'rejected']
    
    def validate(self, trade: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate trade data."""
        self.clear_errors()
        
        if not trade or not isinstance(trade, dict):
            self.add_error("Trade must be a non-empty dictionary")
            return False, self.errors
        
        # Validate trade ID
        if 'trade_id' in trade:
            trade_id = trade['trade_id']
            if not isinstance(trade_id, (str, int)) or not trade_id:
                self.add_error("Trade ID must be a non-empty string or integer")
        
        # Validate symbol
        if 'symbol' not in trade:
            self.add_error("Missing required field: symbol")
        else:
            symbol_validator = SymbolValidator()
            symbol_validator.validate(trade['symbol'])
            self.errors.extend(symbol_validator.errors)
        
        # Validate trade type
        if 'trade_type' in trade:
            trade_type = trade['trade_type']
            if trade_type not in self.trade_types:
                self.add_error(f"Invalid trade_type: {trade_type}. Must be one of {self.trade_types}")
        
        # Validate quantity
        if 'quantity' not in trade:
            self.add_error("Missing required field: quantity")
        else:
            qty = trade['quantity']
            if not isinstance(qty, numbers.Number) or qty <= 0:
                self.add_error("Quantity must be a positive number")
        
        # Validate price
        if 'price' not in trade:
            self.add_error("Missing required field: price")
        else:
            price = trade['price']
            if not isinstance(price, numbers.Number) or price <= 0:
                self.add_error("Price must be a positive number")
        
        # Validate status
        if 'status' in trade:
            status = trade['status']
            if status not in self.trade_statuses:
                self.add_error(f"Invalid status: {status}. Must be one of {self.trade_statuses}")
        
        return self.is_valid(), self.errors


def validate_data(data: Any, validator_type: str = 'data') -> Tuple[bool, List[str]]:
    """
    Validate data using the specified validator.
    
    Args:
        data: Data to validate
        validator_type: Type of validator to use ('data', 'order', 'risk', 'config', 'market', 'time', 'symbol', 'position', 'portfolio', 'trade')
    
    Returns:
        Tuple of (is_valid, errors)
    """
    validators = {
        'data': DataValidator,
        'order': OrderValidator,
        'risk': RiskValidator,
        'config': ConfigValidator,
        'market': MarketDataValidator,
        'time': TimeValidator,
        'symbol': SymbolValidator,
        'position': PositionValidator,
        'portfolio': PortfolioValidator,
        'trade': TradeValidator,
    }
    
    if validator_type not in validators:
        raise ValueError(f"Unknown validator type: {validator_type}")
    
    validator = validators[validator_type]()
    return validator.validate(data)


def is_valid_data(data: Any, validator_type: str = 'data') -> bool:
    """Check if data is valid without returning errors."""
    is_valid, _ = validate_data(data, validator_type)
    return is_valid


def get_validation_errors(data: Any, validator_type: str = 'data') -> List[str]:
    """Get validation errors for data."""
    _, errors = validate_data(data, validator_type)
    return errors


# Export all validators and utility functions
__all__ = [
    'ValidationError',
    'Validator',
    'DataValidator',
    'OrderValidator',
    'RiskValidator',
    'ConfigValidator',
    'MarketDataValidator',
    'TimeValidator',
    'SymbolValidator',
    'PositionValidator',
    'PortfolioValidator',
    'TradeValidator',
    'validate_data',
    'is_valid_data',
    'get_validation_errors',
]

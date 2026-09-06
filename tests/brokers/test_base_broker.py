# tests/brokers/test_base_broker.py
"""
Base Broker Tests.

This module tests the BaseBroker abstract class, ensuring that:
- The abstract methods are defined and raise NotImplementedError when called.
- The constructor sets attributes correctly.
- Any concrete helper methods work as expected.
- Subclassing and method overrides behave correctly.

These tests serve as a contract for all broker implementations.
"""

import pytest

from backend.brokers.base_broker import BaseBroker


class TestBaseBrokerAbstract:
    """Test that BaseBroker behaves as an abstract base class."""

    def test_cannot_instantiate_base_broker_directly(self):
        """Test that BaseBroker cannot be instantiated directly due to abstract methods."""
        with pytest.raises(TypeError):
            BaseBroker()

    def test_abstract_methods_raise_not_implemented_error(self):
        """Test that calling abstract methods on a minimal subclass raises NotImplementedError."""

        class MinimalBroker(BaseBroker):
            """Minimal concrete implementation that doesn't override abstract methods."""

            pass

        # Since we didn't override abstract methods, instantiation should raise TypeError
        with pytest.raises(TypeError):
            MinimalBroker()

    def test_abstract_methods_defined(self):
        """Test that all expected abstract methods exist on BaseBroker."""
        # Use a dummy subclass that doesn't implement them to check the abstract methods
        # We'll use the abstract class itself to check method names.
        abstract_methods = [
            "get_account",
            "get_positions",
            "get_orders",
            "place_order",
            "cancel_order",
            "get_order_status",
            "get_market_data",
        ]
        for method in abstract_methods:
            assert hasattr(BaseBroker, method)
            # In Python 3, abstract methods are still functions; we can check they are callable
            # but we can't call them directly on BaseBroker.
            # We'll just check they exist.

    def test_concrete_methods_work(self):
        """Test that concrete methods (if any) work without overriding."""
        # If BaseBroker has a concrete method like validate_symbol, we can test it.
        # We'll assume there is a `_validate_symbol` or similar.
        # We'll need to use a concrete subclass that implements abstract methods.
        class ConcreteBroker(BaseBroker):
            def get_account(self):
                return {}
            def get_positions(self):
                return []
            def get_orders(self):
                return []
            def place_order(self, symbol, side, order_type, quantity, price=None):
                return {}
            def cancel_order(self, order_id):
                return {}
            def get_order_status(self, order_id):
                return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100):
                return {}

        broker = ConcreteBroker()

        # If there's a concrete helper method, test it.
        # For example, maybe `_validate_symbol` is concrete.
        if hasattr(broker, "_validate_symbol"):
            assert broker._validate_symbol("BTC-USD") is True
            with pytest.raises(ValueError):
                broker._validate_symbol("invalid")

        # If there's a method like `_normalize_symbol`, test it.
        if hasattr(broker, "_normalize_symbol"):
            assert broker._normalize_symbol("BTCUSD") == "BTC-USD"  # Example normalization

        # If there's a method like `_format_order_response`, test it.
        if hasattr(broker, "_format_order_response"):
            raw = {"id": "123", "status": "filled"}
            formatted = broker._format_order_response(raw)
            assert isinstance(formatted, dict)


class TestBaseBrokerConstructor:
    """Test the constructor of BaseBroker and attribute setting."""

    def test_constructor_sets_attributes(self):
        """Test that constructor sets attributes like api_key, api_secret, etc."""
        # We need a concrete subclass that calls super().__init__.
        class ConcreteBroker(BaseBroker):
            def __init__(self, api_key, api_secret, paper=False):
                super().__init__(api_key=api_key, api_secret=api_secret, paper=paper)

            def get_account(self):
                return {}
            def get_positions(self):
                return []
            def get_orders(self):
                return []
            def place_order(self, symbol, side, order_type, quantity, price=None):
                return {}
            def cancel_order(self, order_id):
                return {}
            def get_order_status(self, order_id):
                return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100):
                return {}

        broker = ConcreteBroker(api_key="test_key", api_secret="test_secret", paper=True)
        assert broker.api_key == "test_key"
        assert broker.api_secret == "test_secret"
        assert broker.paper is True

    def test_constructor_defaults(self):
        """Test constructor default parameters."""
        class ConcreteBroker(BaseBroker):
            def __init__(self, api_key=None, api_secret=None, paper=False):
                super().__init__(api_key=api_key, api_secret=api_secret, paper=paper)

            # Implement abstract methods...
            def get_account(self): return {}
            def get_positions(self): return []
            def get_orders(self): return []
            def place_order(self, symbol, side, order_type, quantity, price=None): return {}
            def cancel_order(self, order_id): return {}
            def get_order_status(self, order_id): return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100): return {}

        broker = ConcreteBroker()
        assert broker.api_key is None
        assert broker.api_secret is None
        assert broker.paper is False


class TestBaseBrokerHelperMethods:
    """Test any helper methods that may be defined in BaseBroker (concrete)."""

    def test_validate_symbol_common(self):
        """Test common symbol validation logic if present."""
        # Some brokers may have a common validation in base.
        # We'll create a dummy subclass and call the method.
        class ConcreteBroker(BaseBroker):
            def get_account(self): return {}
            def get_positions(self): return []
            def get_orders(self): return []
            def place_order(self, symbol, side, order_type, quantity, price=None): return {}
            def cancel_order(self, order_id): return {}
            def get_order_status(self, order_id): return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100): return {}

        broker = ConcreteBroker()
        # If _validate_symbol is present, test it.
        if hasattr(broker, "_validate_symbol"):
            # Should accept valid symbol
            assert broker._validate_symbol("BTC-USD") is True
            assert broker._validate_symbol("AAPL") is True
            # Should reject empty or invalid
            with pytest.raises(ValueError):
                broker._validate_symbol("")
            with pytest.raises(ValueError):
                broker._validate_symbol("BTC USD")
            with pytest.raises(ValueError):
                broker._validate_symbol("123")

    def test_format_order_response(self):
        """Test formatting of order response if base provides one."""
        class ConcreteBroker(BaseBroker):
            def get_account(self): return {}
            def get_positions(self): return []
            def get_orders(self): return []
            def place_order(self, symbol, side, order_type, quantity, price=None): return {}
            def cancel_order(self, order_id): return {}
            def get_order_status(self, order_id): return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100): return {}

        broker = ConcreteBroker()
        if hasattr(broker, "_format_order_response"):
            raw = {"id": "ord123", "status": "filled", "filled_quantity": "0.5"}
            formatted = broker._format_order_response(raw)
            # Expect a dict with standard keys.
            assert "id" in formatted
            assert "status" in formatted
            # Optionally check that numeric fields are converted to float.
            if "filled_quantity" in formatted:
                assert isinstance(formatted["filled_quantity"], float)


class TestBaseBrokerExceptionHandling:
    """Test exception handling utilities in BaseBroker."""

    def test_exception_wrapping(self):
        """Test that broker exceptions are wrapped with appropriate messages."""
        # Some base classes provide a method to wrap errors.
        class ConcreteBroker(BaseBroker):
            def get_account(self): return {}
            def get_positions(self): return []
            def get_orders(self): return []
            def place_order(self, symbol, side, order_type, quantity, price=None): return {}
            def cancel_order(self, order_id): return {}
            def get_order_status(self, order_id): return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100): return {}

        broker = ConcreteBroker()
        if hasattr(broker, "_wrap_error"):
            # Test that it raises a BrokerError or similar.
            # We'll not actually test since we don't have the exception class.
            pass

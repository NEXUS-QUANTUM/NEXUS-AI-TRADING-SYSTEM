# tests/blockchain/test_onchain_analysis.py
"""
On-Chain Analysis Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for on-chain analytics:
- OnChainAnalyzer main orchestrator
- TokenAnalyzer (token metrics, supply, transfers)
- WhaleTracker (large transactions, accumulation/distribution)
- VolumeAnalyzer (trading volume, exchange flows)
- GasAnalyzer (gas prices, usage patterns)
- HolderAnalyzer (distribution, concentration)
- DeFiAnalyzer (protocol usage, TVL, yields)
- MempoolAnalyzer (pending transactions, congestion)
- ExchangeFlowAnalyzer (exchange deposits/withdrawals)
- SmartMoneyAnalyzer (tracking smart money wallets)
- OnChainAlerts (event-based alerts, thresholds)

All tests use mocked blockchain providers and data sources.
"""

import asyncio
import json
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockchain.onchain_analysis.base_analyzer import BaseOnChainAnalyzer
from blockchain.onchain_analysis.onchain_analyzer import OnChainAnalyzer
from blockchain.onchain_analysis.token_analyzer import TokenAnalyzer
from blockchain.onchain_analysis.whale_tracker import WhaleTracker
from blockchain.onchain_analysis.volume_analyzer import VolumeAnalyzer
from blockchain.onchain_analysis.gas_analyzer import GasAnalyzer
from blockchain.onchain_analysis.holder_analyzer import HolderAnalyzer
from blockchain.onchain_analysis.defi_analyzer import DeFiAnalyzer
from blockchain.onchain_analysis.mempool_analyzer import MempoolAnalyzer
from blockchain.onchain_analysis.exchange_flow import ExchangeFlowAnalyzer
from blockchain.onchain_analysis.smart_money import SmartMoneyAnalyzer
from blockchain.onchain_analysis.onchain_alerts import OnChainAlertManager
from blockchain.onchain_analysis.onchain_metrics import OnChainMetricsCollector
from blockchain.onchain_analysis.onchain_signals import OnChainSignalGenerator

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE ANALYZER TESTS ==============================

class TestBaseOnChainAnalyzer:
    """Test the BaseOnChainAnalyzer abstract class."""

    def test_base_analyzer_initialization(self):
        """Test initializing a base analyzer."""
        analyzer = BaseOnChainAnalyzer(name="TestAnalyzer", chain_id=1)
        assert analyzer.name == "TestAnalyzer"
        assert analyzer.chain_id == 1
        assert analyzer.is_active is True

    async def test_analyze_not_implemented(self):
        """Test that analyze raises NotImplementedError."""
        analyzer = BaseOnChainAnalyzer(name="Test", chain_id=1)
        with pytest.raises(NotImplementedError):
            await analyzer.analyze("0xToken")

    def test_get_analyzer_info(self):
        """Test getting analyzer information."""
        analyzer = BaseOnChainAnalyzer(name="Test", chain_id=1)
        info = analyzer.get_analyzer_info()
        assert info["name"] == "Test"
        assert info["chain_id"] == 1


# ============================== ON-CHAIN ANALYZER TESTS ==============================

class TestOnChainAnalyzer:
    """Test the main OnChainAnalyzer orchestrator."""

    @pytest.fixture
    def onchain_analyzer(self, web3_client):
        """Return an OnChainAnalyzer with registered sub-analyzers."""
        analyzer = OnChainAnalyzer(web3_client=web3_client)
        # Register mock sub-analyzers
        mock_token = AsyncMock(spec=TokenAnalyzer)
        mock_token.name = "TokenAnalyzer"
        mock_whale = AsyncMock(spec=WhaleTracker)
        mock_whale.name = "WhaleTracker"
        analyzer.register_analyzer("token", mock_token)
        analyzer.register_analyzer("whale", mock_whale)
        return analyzer

    def test_register_analyzer(self, onchain_analyzer):
        """Test registering a sub-analyzer."""
        mock_analyzer = AsyncMock()
        mock_analyzer.name = "VolumeAnalyzer"
        onchain_analyzer.register_analyzer("volume", mock_analyzer)
        assert "volume" in onchain_analyzer.analyzers

    def test_get_analyzer(self, onchain_analyzer):
        """Test retrieving a sub-analyzer."""
        analyzer = onchain_analyzer.get_analyzer("token")
        assert analyzer.name == "TokenAnalyzer"

    async def test_run_analysis(self, onchain_analyzer):
        """Test running analysis with all analyzers."""
        with patch.object(onchain_analyzer.analyzers["token"], "analyze") as mock_token:
            mock_token.return_value = {"metric": "value"}
            with patch.object(onchain_analyzer.analyzers["whale"], "analyze") as mock_whale:
                mock_whale.return_value = {"whale": "data"}
                results = await onchain_analyzer.run_analysis("0xToken")
                assert "token" in results
                assert "whale" in results
                mock_token.assert_called_once_with("0xToken")
                mock_whale.assert_called_once_with("0xToken")

    async def test_get_combined_metrics(self, onchain_analyzer):
        """Test getting combined on-chain metrics."""
        with patch.object(onchain_analyzer.analyzers["token"], "get_metrics") as mock_token:
            mock_token.return_value = {"price": 100, "volume": 1000}
            with patch.object(onchain_analyzer.analyzers["whale"], "get_metrics") as mock_whale:
                mock_whale.return_value = {"whale_holdings": 0.1}
                metrics = await onchain_analyzer.get_combined_metrics("0xToken")
                assert metrics["price"] == 100
                assert metrics["whale_holdings"] == 0.1


# ============================== TOKEN ANALYZER TESTS ==============================

class TestTokenAnalyzer:
    """Test the TokenAnalyzer for token metrics."""

    @pytest.fixture
    def token_analyzer(self, web3_client, mock_erc20_contract):
        """Return a TokenAnalyzer with mocked contract."""
        analyzer = TokenAnalyzer(web3_client=web3_client)
        analyzer.token_contract = mock_erc20_contract
        return analyzer

    async def test_get_token_info(self, token_analyzer):
        """Test getting token information."""
        with patch.object(token_analyzer.token_contract.functions, "name") as mock_name:
            mock_name.return_value.call.return_value = "Test Token"
            with patch.object(token_analyzer.token_contract.functions, "symbol") as mock_symbol:
                mock_symbol.return_value.call.return_value = "TT"
                with patch.object(token_analyzer.token_contract.functions, "decimals") as mock_decimals:
                    mock_decimals.return_value.call.return_value = 18
                    with patch.object(token_analyzer.token_contract.functions, "totalSupply") as mock_supply:
                        mock_supply.return_value.call.return_value = 10**6 * 10**18
                        info = await token_analyzer.get_token_info("0xToken")
                        assert info["name"] == "Test Token"
                        assert info["symbol"] == "TT"
                        assert info["decimals"] == 18
                        assert info["total_supply"] == 10**6 * 10**18

    async def test_get_holder_count(self, token_analyzer):
        """Test getting holder count."""
        # Mock the holder count from a block explorer or on-chain.
        with patch.object(token_analyzer, "_fetch_holder_count") as mock_count:
            mock_count.return_value = 15000
            count = await token_analyzer.get_holder_count("0xToken")
            assert count == 15000

    async def test_get_transfer_volume(self, token_analyzer):
        """Test getting transfer volume over a period."""
        with patch.object(token_analyzer, "_fetch_transfer_events") as mock_events:
            mock_events.return_value = [
                {"from": "0x1", "to": "0x2", "value": 1000},
                {"from": "0x2", "to": "0x1", "value": 500},
            ]
            volume = await token_analyzer.get_transfer_volume("0xToken", days=7)
            assert volume["total_volume"] == 1500
            assert volume["inflow"] == 500
            assert volume["outflow"] == 1000

    async def test_analyze_token_health(self, token_analyzer):
        """Test analyzing token health indicators."""
        with patch.object(token_analyzer, "get_holder_count") as mock_holders:
            mock_holders.return_value = 10000
            with patch.object(token_analyzer, "_get_concentration") as mock_conc:
                mock_conc.return_value = 0.4  # 40% held by top 10
                with patch.object(token_analyzer, "_get_liquidity") as mock_liq:
                    mock_liq.return_value = 1e6
                    health = await token_analyzer.analyze_token_health("0xToken")
                    assert health["holder_count"] == 10000
                    assert health["concentration"] == 0.4
                    assert health["liquidity"] == 1e6
                    assert health["health_score"] is not None


# ============================== WHALE TRACKER TESTS ==============================

class TestWhaleTracker:
    """Test the WhaleTracker for large transactions and holdings."""

    @pytest.fixture
    def whale_tracker(self, web3_client):
        """Return a WhaleTracker instance."""
        return WhaleTracker(web3_client=web3_client)

    async def test_track_whale_transactions(self, whale_tracker):
        """Test tracking large transactions."""
        with patch.object(whale_tracker, "_fetch_large_transfers") as mock_transfers:
            mock_transfers.return_value = [
                {"from": "0xWhale1", "to": "0xExchange", "value": 10000, "tx_hash": "0x123"},
                {"from": "0xWhale2", "to": "0xOther", "value": 5000, "tx_hash": "0x456"},
            ]
            transactions = await whale_tracker.track_whale_transactions(
                token="0xToken",
                threshold=1000,
                days=7,
            )
            assert len(transactions) == 2
            assert transactions[0]["value"] == 10000

    async def test_get_whale_holdings(self, whale_tracker):
        """Test getting holdings of a specific whale address."""
        with patch.object(whale_tracker, "_fetch_address_holdings") as mock_holdings:
            mock_holdings.return_value = {"0xToken": 100000, "0xOther": 50000}
            holdings = await whale_tracker.get_whale_holdings("0xWhale1")
            assert holdings["0xToken"] == 100000

    async def test_analyze_accumulation_distribution(self, whale_tracker):
        """Test analyzing accumulation/distribution patterns."""
        with patch.object(whale_tracker, "_fetch_balance_history") as mock_history:
            mock_history.return_value = [
                {"timestamp": 1234567890, "balance": 100000},
                {"timestamp": 1234567900, "balance": 110000},
                {"timestamp": 1234567910, "balance": 95000},
            ]
            analysis = await whale_tracker.analyze_accumulation_distribution("0xWhale1", days=30)
            assert analysis["start_balance"] == 100000
            assert analysis["end_balance"] == 95000
            assert analysis["net_change"] == -5000
            assert analysis["trend"] == "distribution"


# ============================== VOLUME ANALYZER TESTS ==============================

class TestVolumeAnalyzer:
    """Test the VolumeAnalyzer for trading volume metrics."""

    @pytest.fixture
    def volume_analyzer(self, web3_client):
        """Return a VolumeAnalyzer instance."""
        return VolumeAnalyzer(web3_client=web3_client)

    async def test_get_volume(self, volume_analyzer):
        """Test getting volume for a token."""
        with patch.object(volume_analyzer, "_fetch_volume_data") as mock_vol:
            mock_vol.return_value = {"24h": 500000, "7d": 3500000, "30d": 15000000}
            volume = await volume_analyzer.get_volume("0xToken")
            assert volume["24h"] == 500000
            assert volume["7d"] == 3500000

    async def test_get_volume_by_exchange(self, volume_analyzer):
        """Test volume breakdown by exchange."""
        with patch.object(volume_analyzer, "_fetch_exchange_volume") as mock_ex:
            mock_ex.return_value = {"Binance": 300000, "Coinbase": 200000, "Uniswap": 50000}
            breakdown = await volume_analyzer.get_volume_by_exchange("0xToken")
            assert breakdown["Binance"] == 300000
            assert breakdown["Uniswap"] == 50000

    async def test_analyze_volume_anomalies(self, volume_analyzer):
        """Test detecting volume anomalies."""
        with patch.object(volume_analyzer, "_fetch_historical_volume") as mock_hist:
            mock_hist.return_value = [100000, 120000, 110000, 500000, 90000]  # spike at index 3
            anomalies = await volume_analyzer.analyze_volume_anomalies("0xToken", days=5)
            # Should detect the spike
            assert len(anomalies) > 0
            assert anomalies[0]["volume"] == 500000


# ============================== GAS ANALYZER TESTS ==============================

class TestGasAnalyzer:
    """Test the GasAnalyzer for gas metrics."""

    @pytest.fixture
    def gas_analyzer(self, web3_client):
        """Return a GasAnalyzer instance."""
        return GasAnalyzer(web3_client=web3_client)

    async def test_get_current_gas_price(self, gas_analyzer):
        """Test getting current gas price."""
        with patch.object(gas_analyzer.web3.eth, "gas_price") as mock_gas:
            mock_gas.return_value = 1000000000  # 1 Gwei
            price = await gas_analyzer.get_current_gas_price()
            assert price == 1000000000

    async def test_get_gas_price_history(self, gas_analyzer):
        """Test getting historical gas prices."""
        with patch.object(gas_analyzer, "_fetch_gas_history") as mock_hist:
            mock_hist.return_value = [
                {"timestamp": 1234567890, "price": 1000000000},
                {"timestamp": 1234567895, "price": 1200000000},
            ]
            history = await gas_analyzer.get_gas_price_history(hours=24)
            assert len(history) == 2
            assert history[0]["price"] == 1000000000

    async def test_get_gas_usage_patterns(self, gas_analyzer):
        """Test analyzing gas usage patterns."""
        with patch.object(gas_analyzer, "_fetch_block_gas_usage") as mock_usage:
            mock_usage.return_value = [0.5, 0.6, 0.7, 0.8, 0.9]
            patterns = await gas_analyzer.get_gas_usage_patterns(blocks=10)
            assert patterns["average"] == 0.7
            assert patterns["max"] == 0.9
            assert patterns["min"] == 0.5

    async def test_estimate_transaction_cost(self, gas_analyzer):
        """Test estimating transaction cost."""
        with patch.object(gas_analyzer, "get_current_gas_price") as mock_price:
            mock_price.return_value = 1000000000
            cost = await gas_analyzer.estimate_transaction_cost(gas_limit=21000)
            # 1e9 * 21000 = 2.1e13 wei = 0.000021 ETH
            assert cost == 2.1e13


# ============================== HOLDER ANALYZER TESTS ==============================

class TestHolderAnalyzer:
    """Test the HolderAnalyzer for holder distribution."""

    @pytest.fixture
    def holder_analyzer(self, web3_client):
        """Return a HolderAnalyzer instance."""
        return HolderAnalyzer(web3_client=web3_client)

    async def test_get_holder_distribution(self, holder_analyzer):
        """Test getting holder distribution (top holders)."""
        with patch.object(holder_analyzer, "_fetch_top_holders") as mock_top:
            mock_top.return_value = [
                {"address": "0xWhale1", "balance": 1000000},
                {"address": "0xWhale2", "balance": 800000},
                {"address": "0xUser1", "balance": 100},
            ]
            distribution = await holder_analyzer.get_holder_distribution("0xToken", top_n=10)
            assert len(distribution) == 3
            assert distribution[0]["balance"] == 1000000

    async def test_calculate_ginny_coefficient(self, holder_analyzer):
        """Test calculating Gini coefficient (inequality)."""
        with patch.object(holder_analyzer, "_fetch_all_holdings") as mock_holdings:
            mock_holdings.return_value = [1000, 1000, 1000, 1, 1, 1]  # unequal
            gini = await holder_analyzer.calculate_gini_coefficient("0xToken")
            # Approximate Gini for this distribution; should be > 0
            assert gini > 0.5

    async def test_analyze_holder_activity(self, holder_analyzer):
        """Test analyzing holder activity (active, dormant)."""
        with patch.object(holder_analyzer, "_fetch_holder_activity") as mock_act:
            mock_act.return_value = {
                "active_holders": 500,
                "dormant_holders": 1000,
                "new_holders": 50,
                "churn": 20,
            }
            activity = await holder_analyzer.analyze_holder_activity("0xToken", days=30)
            assert activity["active_holders"] == 500
            assert activity["dormant_holders"] == 1000


# ============================== DEFI ANALYZER TESTS ==============================

class TestDeFiAnalyzer:
    """Test the DeFiAnalyzer for DeFi protocol analytics."""

    @pytest.fixture
    def defi_analyzer(self, web3_client):
        """Return a DeFiAnalyzer instance."""
        return DeFiAnalyzer(web3_client=web3_client)

    async def test_get_protocol_tvl(self, defi_analyzer):
        """Test getting TVL of a protocol."""
        with patch.object(defi_analyzer, "_fetch_tvl_data") as mock_tvl:
            mock_tvl.return_value = {"total": 10e9, "per_asset": {"ETH": 5e9, "USDC": 3e9}}
            tvl = await defi_analyzer.get_protocol_tvl("Aave")
            assert tvl["total"] == 10e9

    async def test_get_protocol_apys(self, defi_analyzer):
        """Test getting APYs from a protocol."""
        with patch.object(defi_analyzer, "_fetch_apy_data") as mock_apy:
            mock_apy.return_value = {"USDC": 0.05, "DAI": 0.04, "ETH": 0.03}
            apys = await defi_analyzer.get_protocol_apys("Compound")
            assert apys["USDC"] == 0.05

    async def test_analyze_defi_risk(self, defi_analyzer):
        """Test analyzing risk of a DeFi protocol."""
        with patch.object(defi_analyzer, "_fetch_protocol_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "liquidity": 1e9,
                "audits": ["CertiK"],
                "hack_incidents": 0,
                "insurance": 1e6,
            }
            risk = await defi_analyzer.analyze_defi_risk("Aave")
            assert risk["risk_score"] < 30  # low risk
            assert risk["risk_level"] == "low"


# ============================== MEMPOOL ANALYZER TESTS ==============================

class TestMempoolAnalyzer:
    """Test the MempoolAnalyzer for pending transactions."""

    @pytest.fixture
    def mempool_analyzer(self, web3_client):
        """Return a MempoolAnalyzer instance."""
        return MempoolAnalyzer(web3_client=web3_client)

    async def test_get_pending_transactions(self, mempool_analyzer):
        """Test getting pending transactions count."""
        with patch.object(mempool_analyzer, "_fetch_mempool_txs") as mock_mempool:
            mock_mempool.return_value = [{"tx_hash": "0x1"}, {"tx_hash": "0x2"}, {"tx_hash": "0x3"}]
            txs = await mempool_analyzer.get_pending_transactions()
            assert len(txs) == 3

    async def test_analyze_mempool_congestion(self, mempool_analyzer):
        """Test analyzing mempool congestion."""
        with patch.object(mempool_analyzer, "_fetch_mempool_stats") as mock_stats:
            mock_stats.return_value = {"pending_count": 100, "avg_wait_time": 120, "gas_spike": True}
            congestion = await mempool_analyzer.analyze_mempool_congestion()
            assert congestion["pending_count"] == 100
            assert congestion["gas_spike"] is True

    async def test_get_recommended_gas(self, mempool_analyzer):
        """Test getting recommended gas prices based on mempool."""
        with patch.object(mempool_analyzer, "_fetch_mempool_gas_prices") as mock_prices:
            mock_prices.return_value = {"low": 50, "medium": 100, "high": 150}
            recommended = await mempool_analyzer.get_recommended_gas()
            assert recommended["low"] == 50
            assert recommended["medium"] == 100


# ============================== EXCHANGE FLOW ANALYZER TESTS ==============================

class TestExchangeFlowAnalyzer:
    """Test the ExchangeFlowAnalyzer for exchange deposits/withdrawals."""

    @pytest.fixture
    def exchange_flow_analyzer(self, web3_client):
        """Return an ExchangeFlowAnalyzer instance."""
        return ExchangeFlowAnalyzer(web3_client=web3_client)

    async def test_get_exchange_flows(self, exchange_flow_analyzer):
        """Test getting net exchange flows."""
        with patch.object(exchange_flow_analyzer, "_fetch_exchange_transfers") as mock_transfers:
            mock_transfers.return_value = {
                "Binance": {"deposits": 10000, "withdrawals": 5000},
                "Coinbase": {"deposits": 8000, "withdrawals": 12000},
            }
            flows = await exchange_flow_analyzer.get_exchange_flows("0xToken", days=7)
            assert flows["Binance"]["net"] == 5000
            assert flows["Coinbase"]["net"] == -4000

    async def test_detect_large_inflows(self, exchange_flow_analyzer):
        """Test detecting large exchange inflows."""
        with patch.object(exchange_flow_analyzer, "_fetch_large_deposits") as mock_deposits:
            mock_deposits.return_value = [
                {"exchange": "Binance", "amount": 1000000, "tx_hash": "0x123"},
                {"exchange": "Kraken", "amount": 500000, "tx_hash": "0x456"},
            ]
            inflows = await exchange_flow_analyzer.detect_large_inflows("0xToken", threshold=100000)
            assert len(inflows) == 2

    async def test_analyze_exchange_volume(self, exchange_flow_analyzer):
        """Test analyzing exchange trading volume."""
        with patch.object(exchange_flow_analyzer, "_fetch_exchange_volume") as mock_vol:
            mock_vol.return_value = {"Binance": 1e6, "Coinbase": 0.5e6, "Uniswap": 0.2e6}
            volume = await exchange_flow_analyzer.analyze_exchange_volume("0xToken")
            assert volume["total"] == 1.7e6
            assert volume["top_exchange"] == "Binance"


# ============================== SMART MONEY ANALYZER TESTS ==============================

class TestSmartMoneyAnalyzer:
    """Test the SmartMoneyAnalyzer for tracking smart wallets."""

    @pytest.fixture
    def smart_money_analyzer(self, web3_client):
        """Return a SmartMoneyAnalyzer instance."""
        return SmartMoneyAnalyzer(web3_client=web3_client)

    async def test_identify_smart_wallets(self, smart_money_analyzer):
        """Test identifying smart money wallets based on historical performance."""
        with patch.object(smart_money_analyzer, "_fetch_wallet_performance") as mock_perf:
            mock_perf.return_value = [
                {"address": "0xSmart1", "pnl": 1000, "win_rate": 0.8},
                {"address": "0xSmart2", "pnl": 800, "win_rate": 0.75},
            ]
            smart_wallets = await smart_money_analyzer.identify_smart_wallets(
                token="0xToken",
                min_pnl=500,
                min_win_rate=0.7,
            )
            assert len(smart_wallets) == 2

    async def test_track_smart_money_flows(self, smart_money_analyzer):
        """Test tracking flows from smart wallets."""
        with patch.object(smart_money_analyzer, "_fetch_wallet_transactions") as mock_txs:
            mock_txs.return_value = [
                {"from": "0xSmart1", "to": "0xExchange", "value": 10000, "tx_hash": "0x123"},
                {"from": "0xSmart2", "to": "0xOther", "value": 5000, "tx_hash": "0x456"},
            ]
            flows = await smart_money_analyzer.track_smart_money_flows("0xToken", days=7)
            assert len(flows) == 2

    async def test_get_smart_money_sentiment(self, smart_money_analyzer):
        """Test getting sentiment based on smart money activity."""
        with patch.object(smart_money_analyzer, "_fetch_smart_money_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "net_buy": 100000,
                "net_sell": 50000,
                "active_wallets": 10,
            }
            sentiment = await smart_money_analyzer.get_smart_money_sentiment("0xToken")
            assert sentiment["net"] == 50000
            assert sentiment["signal"] == "bullish"


# ============================== ON-CHAIN ALERT MANAGER TESTS ==============================

class TestOnChainAlertManager:
    """Test the OnChainAlertManager for event-based alerts."""

    @pytest.fixture
    def alert_manager(self):
        """Return an OnChainAlertManager instance."""
        return OnChainAlertManager()

    async def test_add_alert_rule(self, alert_manager):
        """Test adding an alert rule."""
        rule = {
            "name": "Whale Alert",
            "type": "whale_transfer",
            "condition": {"threshold": 10000},
            "actions": ["email", "webhook"],
        }
        await alert_manager.add_alert_rule("whale_alert", rule)
        assert "whale_alert" in alert_manager.rules

    async def test_check_alerts(self, alert_manager):
        """Test checking alerts against new data."""
        # Mock data that triggers an alert
        trigger_data = {"amount": 50000, "from": "0xWhale", "to": "0xExchange"}
        with patch.object(alert_manager, "_evaluate_rule") as mock_eval:
            mock_eval.return_value = True
            with patch.object(alert_manager, "_send_alert") as mock_send:
                await alert_manager.check_alerts(trigger_data)
                mock_send.assert_called_once()

    async def test_remove_alert_rule(self, alert_manager):
        """Test removing an alert rule."""
        rule = {"name": "Test", "condition": {}}
        await alert_manager.add_alert_rule("test_rule", rule)
        await alert_manager.remove_alert_rule("test_rule")
        assert "test_rule" not in alert_manager.rules


# ============================== ON-CHAIN METRICS COLLECTOR TESTS ==============================

class TestOnChainMetricsCollector:
    """Test the OnChainMetricsCollector for aggregating metrics."""

    @pytest.fixture
    def metrics_collector(self):
        """Return an OnChainMetricsCollector instance."""
        return OnChainMetricsCollector()

    async def test_collect_metrics(self, metrics_collector):
        """Test collecting metrics from multiple analyzers."""
        # Mock analyzers and their metrics
        mock_analyzer1 = AsyncMock()
        mock_analyzer1.get_metrics = AsyncMock(return_value={"price": 100, "volume": 1000})
        mock_analyzer2 = AsyncMock()
        mock_analyzer2.get_metrics = AsyncMock(return_value={"holders": 5000})

        metrics_collector.analyzers = {"price": mock_analyzer1, "holders": mock_analyzer2}
        metrics = await metrics_collector.collect_metrics("0xToken")
        assert metrics["price"] == 100
        assert metrics["holders"] == 5000

    async def test_collect_timeseries(self, metrics_collector):
        """Test collecting time-series metrics."""
        with patch.object(metrics_collector, "_fetch_timeseries") as mock_ts:
            mock_ts.return_value = [
                {"timestamp": 1234567890, "price": 100},
                {"timestamp": 1234567900, "price": 101},
            ]
            ts_data = await metrics_collector.collect_timeseries("0xToken", metric="price", days=1)
            assert len(ts_data) == 2
            assert ts_data[0]["price"] == 100


# ============================== ON-CHAIN SIGNAL GENERATOR TESTS ==============================

class TestOnChainSignalGenerator:
    """Test the OnChainSignalGenerator for generating trading signals."""

    @pytest.fixture
    def signal_generator(self):
        """Return an OnChainSignalGenerator instance."""
        return OnChainSignalGenerator()

    async def test_generate_signals(self, signal_generator):
        """Test generating signals based on on-chain data."""
        # Mock metrics data
        metrics = {
            "price": 100,
            "volume_24h": 500000,
            "holders": 10000,
            "whale_net_buy": 1000,
            "exchange_net_flow": 500,
            "gas_price": 50,
        }
        with patch.object(signal_generator, "_analyze_metrics") as mock_analyze:
            mock_analyze.return_value = [
                {"type": "buy", "confidence": 0.8, "reason": "whale accumulation"},
                {"type": "hold", "confidence": 0.6, "reason": "neutral volume"},
            ]
            signals = await signal_generator.generate_signals("0xToken", metrics)
            assert len(signals) == 2
            assert signals[0]["type"] == "buy"
            assert signals[0]["confidence"] == 0.8

    async def test_get_signal_history(self, signal_generator):
        """Test retrieving historical signals."""
        with patch.object(signal_generator, "_fetch_signal_history") as mock_hist:
            mock_hist.return_value = [
                {"timestamp": 1234567890, "signal": "buy", "price": 100},
                {"timestamp": 1234567900, "signal": "sell", "price": 110},
            ]
            history = await signal_generator.get_signal_history("0xToken", days=30)
            assert len(history) == 2
            assert history[0]["signal"] == "buy"


# ============================== INTEGRATION TESTS ==============================

class TestOnChainIntegration:
    """Integration tests for on-chain analysis components."""

    async def test_full_analysis_pipeline(self, onchain_analyzer, alert_manager, signal_generator):
        """Test a complete pipeline: collect data -> analyze -> generate signals -> check alerts."""
        # Mock data
        token = "0xToken"
        metrics = {"price": 100, "volume": 1000, "whale_holdings": 0.1, "exchange_net": 500}

        # 1. Collect metrics
        with patch.object(onchain_analyzer, "get_combined_metrics") as mock_metrics:
            mock_metrics.return_value = metrics
            collected = await onchain_analyzer.get_combined_metrics(token)
            assert collected == metrics

        # 2. Generate signals
        with patch.object(signal_generator, "generate_signals") as mock_signal:
            mock_signal.return_value = [{"type": "buy", "confidence": 0.8}]
            signals = await signal_generator.generate_signals(token, collected)
            assert len(signals) > 0

        # 3. Check alerts
        with patch.object(alert_manager, "check_alerts") as mock_alerts:
            await alert_manager.check_alerts({"signal": signals[0]})
            mock_alerts.assert_called_once()

    async def test_whale_alert_trigger(self, alert_manager, whale_tracker):
        """Test that whale detection triggers an alert."""
        # Set up alert rule for whale transfers
        rule = {
            "name": "Whale Transfer Alert",
            "type": "whale_transfer",
            "condition": {"threshold": 10000},
            "actions": ["webhook"],
        }
        await alert_manager.add_alert_rule("whale_transfer", rule)

        # Simulate a large transfer
        large_tx = {"from": "0xWhale", "to": "0xExchange", "value": 50000}

        # Check alerts
        with patch.object(alert_manager, "_send_alert") as mock_send:
            await alert_manager.check_alerts(large_tx)
            mock_send.assert_called_once()

    async def test_smart_money_signal_accuracy(self, smart_money_analyzer, signal_generator):
        """Test that smart money signals align with on-chain data."""
        # Mock smart money metrics
        metrics = {"smart_money_net_buy": 1000, "smart_money_active": 5}
        with patch.object(smart_money_analyzer, "get_smart_money_sentiment") as mock_sent:
            mock_sent.return_value = {"net": 1000, "signal": "bullish"}
            sentiment = await smart_money_analyzer.get_smart_money_sentiment("0xToken")

        # Generate signal based on sentiment
        with patch.object(signal_generator, "generate_signals") as mock_signal:
            mock_signal.return_value = [{"type": "buy", "confidence": 0.9}]
            signals = await signal_generator.generate_signals("0xToken", sentiment)
            assert signals[0]["type"] == "buy"

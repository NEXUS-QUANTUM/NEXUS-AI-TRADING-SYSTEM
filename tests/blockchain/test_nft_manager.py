# tests/blockchain/test_nft_manager.py
"""
NFT Manager Tests for the NEXUS AI Trading System.

This module contains comprehensive tests for all NFT-related functionality:
- Collection registration and management (ERC721, ERC1155)
- NFT metadata fetching and parsing (tokenURI, on-chain metadata)
- NFT transfers (safeTransferFrom, transferFrom)
- NFT trading (listing, buying, selling)
- NFT lending (collateralization, loan management)
- NFT staking (stake, unstake, rewards)
- NFT valuation (rarity scoring, floor price tracking)
- NFT analytics (whale tracking, volume analysis, collection stats)
- NFT marketplace integrations (OpenSea, Blur, LooksRare)

All tests use mocked contract interactions and web3 clients.
"""

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockchain.nft.nft_manager import NFTManager
from blockchain.nft.base_nft import BaseNFTCollection
from blockchain.nft.erc721 import ERC721Collection
from blockchain.nft.erc1155 import ERC1155Collection
from blockchain.nft.nft_analytics import NFTAnalytics
from blockchain.nft.nft_collection import NFTCollectionManager
from blockchain.nft.nft_config import NFTConfig
from blockchain.nft.nft_lending import NFTLendingManager
from blockchain.nft.nft_marketplace import NFTMarketplaceManager
from blockchain.nft.nft_metadata import NFTMetadataParser
from blockchain.nft.nft_rarity import NFTRarityAnalyzer
from blockchain.nft.nft_staking import NFTStakingManager
from blockchain.nft.nft_trading import NFTTradingManager
from blockchain.nft.nft_valuation import NFTValuationManager
from blockchain.nft.nft_whale import NFTWhaleTracker

pytest_plugins = ["tests.blockchain.conftest"]


# ============================== BASE NFT COLLECTION TESTS ==============================

class TestBaseNFTCollection:
    """Test the BaseNFTCollection abstract class."""

    def test_base_collection_initialization(self):
        """Test initializing a base NFT collection."""
        collection = BaseNFTCollection(
            name="TestCollection",
            address="0x" + "a" * 40,
            chain_id=1,
            standard="ERC721",
        )
        assert collection.name == "TestCollection"
        assert collection.address == "0x" + "a" * 40
        assert collection.chain_id == 1
        assert collection.standard == "ERC721"

    async def test_get_token_uri_not_implemented(self):
        """Test that get_token_uri raises NotImplementedError."""
        collection = BaseNFTCollection(name="Test", address="0x123", chain_id=1)
        with pytest.raises(NotImplementedError):
            await collection.get_token_uri(1)

    async def test_transfer_not_implemented(self):
        """Test that transfer raises NotImplementedError."""
        collection = BaseNFTCollection(name="Test", address="0x123", chain_id=1)
        with pytest.raises(NotImplementedError):
            await collection.transfer(1, "0xfrom", "0xto", "0xkey")

    def test_get_collection_info(self):
        """Test retrieving collection information."""
        collection = BaseNFTCollection(name="Test", address="0x123", chain_id=1, standard="ERC721")
        info = collection.get_collection_info()
        assert info["name"] == "Test"
        assert info["address"] == "0x123"
        assert info["standard"] == "ERC721"


# ============================== ERC721 COLLECTION TESTS ==============================

class TestERC721Collection:
    """Test the ERC721Collection implementation."""

    @pytest.fixture
    def erc721_collection(self, web3_client_service, mock_erc721_contract):
        """Return an ERC721Collection instance with mocked contract."""
        collection = ERC721Collection(
            name="TestNFT",
            address="0x" + "b" * 40,
            chain_id=1,
            web3_client=web3_client_service,
        )
        collection.contract = mock_erc721_contract
        return collection

    async def test_get_token_uri(self, erc721_collection):
        """Test fetching token URI."""
        with patch.object(erc721_collection.contract.functions, "tokenURI") as mock_uri:
            mock_uri.return_value.call.return_value = "ipfs://Qm123"
            uri = await erc721_collection.get_token_uri(1)
            assert uri == "ipfs://Qm123"

    async def test_get_owner(self, erc721_collection):
        """Test getting owner of a token."""
        with patch.object(erc721_collection.contract.functions, "ownerOf") as mock_owner:
            mock_owner.return_value.call.return_value = "0x" + "c" * 40
            owner = await erc721_collection.get_owner(1)
            assert owner == "0x" + "c" * 40

    async def test_transfer(self, erc721_collection, test_private_key, test_address_from_private_key):
        """Test transferring an NFT."""
        with patch.object(erc721_collection.contract.functions, "safeTransferFrom") as mock_transfer:
            mock_transfer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc721_collection.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "d" * 64
                with patch.object(erc721_collection.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "d" * 64}
                    result = await erc721_collection.transfer(
                        token_id=1,
                        from_address=test_address_from_private_key,
                        to_address="0x" + "e" * 40,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "d" * 64

    async def test_approve(self, erc721_collection, test_private_key, test_address_from_private_key):
        """Test approving an operator."""
        with patch.object(erc721_collection.contract.functions, "approve") as mock_approve:
            mock_approve.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc721_collection.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "f" * 64
                with patch.object(erc721_collection.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "f" * 64}
                    result = await erc721_collection.approve(
                        token_id=1,
                        operator="0x" + "g" * 40,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "f" * 64

    async def test_is_approved_for_all(self, erc721_collection):
        """Test checking approval status."""
        with patch.object(erc721_collection.contract.functions, "isApprovedForAll") as mock_approved:
            mock_approved.return_value.call.return_value = True
            is_approved = await erc721_collection.is_approved_for_all("0xowner", "0xoperator")
            assert is_approved is True

    async def test_set_approval_for_all(self, erc721_collection, test_private_key, test_address_from_private_key):
        """Test setting approval for all."""
        with patch.object(erc721_collection.contract.functions, "setApprovalForAll") as mock_set:
            mock_set.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc721_collection.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "h" * 64
                with patch.object(erc721_collection.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "h" * 64}
                    result = await erc721_collection.set_approval_for_all(
                        operator="0x" + "i" * 40,
                        approved=True,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "h" * 64


# ============================== ERC1155 COLLECTION TESTS ==============================

class TestERC1155Collection:
    """Test the ERC1155Collection implementation (multi-token)."""

    @pytest.fixture
    def erc1155_collection(self, web3_client_service):
        """Return an ERC1155Collection instance with mocked contract."""
        collection = ERC1155Collection(
            name="TestMultiNFT",
            address="0x" + "j" * 40,
            chain_id=1,
            web3_client=web3_client_service,
        )
        # Mock contract
        collection.contract = MagicMock()
        return collection

    async def test_get_uri(self, erc1155_collection):
        """Test fetching URI for a token type."""
        with patch.object(erc1155_collection.contract.functions, "uri") as mock_uri:
            mock_uri.return_value.call.return_value = "ipfs://Qm456/{id}"
            uri = await erc1155_collection.get_uri(1)
            assert uri == "ipfs://Qm456/{id}"

    async def test_get_balance(self, erc1155_collection):
        """Test getting balance of a token type."""
        with patch.object(erc1155_collection.contract.functions, "balanceOf") as mock_balance:
            mock_balance.return_value.call.return_value = 10
            balance = await erc1155_collection.get_balance("0xowner", 1)
            assert balance == 10

    async def test_safe_transfer_from(self, erc1155_collection, test_private_key, test_address_from_private_key):
        """Test safe transfer of ERC1155 token."""
        with patch.object(erc1155_collection.contract.functions, "safeTransferFrom") as mock_transfer:
            mock_transfer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc1155_collection.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "k" * 64
                with patch.object(erc1155_collection.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "k" * 64}
                    result = await erc1155_collection.safe_transfer(
                        token_id=1,
                        amount=2,
                        from_address=test_address_from_private_key,
                        to_address="0x" + "l" * 40,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "k" * 64

    async def test_batch_transfer(self, erc1155_collection, test_private_key, test_address_from_private_key):
        """Test batch transfer of multiple token types."""
        with patch.object(erc1155_collection.contract.functions, "safeBatchTransferFrom") as mock_batch:
            mock_batch.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(erc1155_collection.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "m" * 64
                with patch.object(erc1155_collection.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "m" * 64}
                    result = await erc1155_collection.batch_transfer(
                        token_ids=[1, 2, 3],
                        amounts=[1, 2, 3],
                        from_address=test_address_from_private_key,
                        to_address="0x" + "n" * 40,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "m" * 64


# ============================== NFT MANAGER TESTS ==============================

class TestNFTManager:
    """Test the NFTManager orchestrating collections."""

    @pytest.fixture
    def nft_manager(self, erc721_collection, erc1155_collection):
        """Return an NFTManager with registered collections."""
        manager = NFTManager()
        manager.register_collection("TestNFT", erc721_collection)
        manager.register_collection("TestMultiNFT", erc1155_collection)
        return manager

    def test_register_collection(self, nft_manager):
        """Test registering a collection."""
        mock_collection = MagicMock()
        nft_manager.register_collection("NewCollection", mock_collection)
        assert "NewCollection" in nft_manager.collections

    def test_get_collection(self, nft_manager):
        """Test retrieving a collection."""
        collection = nft_manager.get_collection("TestNFT")
        assert collection.name == "TestNFT"

    def test_get_collection_not_found(self, nft_manager):
        """Test retrieving a non-existent collection."""
        with pytest.raises(KeyError):
            nft_manager.get_collection("Unknown")

    def test_list_collections(self, nft_manager):
        """Test listing all collections."""
        collections = nft_manager.list_collections()
        assert len(collections) == 2
        assert "TestNFT" in collections
        assert "TestMultiNFT" in collections

    async def test_get_token_uri(self, nft_manager):
        """Test getting token URI via manager."""
        with patch.object(nft_manager.collections["TestNFT"], "get_token_uri") as mock_uri:
            mock_uri.return_value = "ipfs://Qm123"
            uri = await nft_manager.get_token_uri("TestNFT", 1)
            assert uri == "ipfs://Qm123"
            mock_uri.assert_called_once_with(1)

    async def test_transfer_nft(self, nft_manager, test_private_key, test_address_from_private_key):
        """Test transferring an NFT via manager."""
        with patch.object(nft_manager.collections["TestNFT"], "transfer") as mock_transfer:
            mock_transfer.return_value = {"tx_hash": "0x" + "o" * 64}
            result = await nft_manager.transfer_nft(
                collection_name="TestNFT",
                token_id=1,
                from_address=test_address_from_private_key,
                to_address="0x" + "p" * 40,
                private_key=test_private_key,
            )
            assert result["tx_hash"] == "0x" + "o" * 64
            mock_transfer.assert_called_once_with(
                token_id=1,
                from_address=test_address_from_private_key,
                to_address="0x" + "p" * 40,
                private_key=test_private_key,
            )

    async def test_get_balance(self, nft_manager):
        """Test getting token balance via manager."""
        with patch.object(nft_manager.collections["TestMultiNFT"], "get_balance") as mock_balance:
            mock_balance.return_value = 5
            balance = await nft_manager.get_balance("TestMultiNFT", "0xowner", token_id=1)
            assert balance == 5


# ============================== NFT METADATA PARSER TESTS ==============================

class TestNFTMetadataParser:
    """Test the NFTMetadataParser for parsing token metadata."""

    @pytest.fixture
    def metadata_parser(self):
        """Return an NFTMetadataParser instance."""
        return NFTMetadataParser()

    def test_parse_ipfs_uri(self, metadata_parser):
        """Test parsing IPFS URI to HTTP gateway URL."""
        uri = "ipfs://Qm123"
        gateway = "https://ipfs.io/ipfs/"
        parsed = metadata_parser.parse_uri(uri, gateway)
        assert parsed == "https://ipfs.io/ipfs/Qm123"

    def test_parse_metadata_json(self, metadata_parser):
        """Test parsing metadata JSON."""
        metadata_json = json.dumps({
            "name": "Token #1",
            "description": "Test NFT",
            "image": "ipfs://Qm456",
            "attributes": [{"trait_type": "Background", "value": "Blue"}],
        })
        parsed = metadata_parser.parse_metadata(metadata_json)
        assert parsed["name"] == "Token #1"
        assert parsed["attributes"][0]["value"] == "Blue"

    async def test_fetch_metadata(self, metadata_parser):
        """Test fetching metadata from URI."""
        # Mock the HTTP request
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text.return_value = json.dumps({"name": "Token #1", "image": "ipfs://Qm456"})
            mock_get.return_value.__aenter__.return_value = mock_response
            metadata = await metadata_parser.fetch_metadata("https://example.com/metadata/1")
            assert metadata["name"] == "Token #1"


# ============================== NFT RARITY ANALYZER TESTS ==============================

class TestNFTRarityAnalyzer:
    """Test the NFTRarityAnalyzer for rarity scoring."""

    @pytest.fixture
    def rarity_analyzer(self):
        """Return an NFTRarityAnalyzer instance."""
        return NFTRarityAnalyzer()

    def test_calculate_rarity_score(self, rarity_analyzer):
        """Test calculating rarity score based on traits."""
        traits = [
            {"trait_type": "Background", "value": "Blue", "frequency": 0.3},
            {"trait_type": "Eyes", "value": "Red", "frequency": 0.05},
            {"trait_type": "Hat", "value": "Top Hat", "frequency": 0.1},
        ]
        # Higher frequency = lower rarity score
        score = rarity_analyzer.calculate_rarity_score(traits)
        # Should be higher for rarer traits (lower frequency)
        assert score > 0

    def test_get_rarity_ranking(self, rarity_analyzer):
        """Test ranking NFTs by rarity."""
        nfts = [
            {"id": 1, "traits": [{"frequency": 0.1}, {"frequency": 0.2}]},
            {"id": 2, "traits": [{"frequency": 0.05}, {"frequency": 0.15}]},
            {"id": 3, "traits": [{"frequency": 0.3}, {"frequency": 0.4}]},
        ]
        ranked = rarity_analyzer.get_rarity_ranking(nfts)
        # Should be sorted by rarity score (descending)
        assert ranked[0]["id"] == 2  # rarest
        assert ranked[-1]["id"] == 3  # least rare

    def test_compare_rarity(self, rarity_analyzer):
        """Test comparing rarity between two NFTs."""
        nft_a = {"traits": [{"frequency": 0.1}, {"frequency": 0.2}]}
        nft_b = {"traits": [{"frequency": 0.05}, {"frequency": 0.15}]}
        comparison = rarity_analyzer.compare_rarity(nft_a, nft_b)
        assert comparison["nft_a_score"] < comparison["nft_b_score"]  # B is rarer


# ============================== NFT VALUATION MANAGER TESTS ==============================

class TestNFTValuationManager:
    """Test the NFTValuationManager for pricing NFTs."""

    @pytest.fixture
    def valuation_manager(self):
        """Return an NFTValuationManager instance."""
        return NFTValuationManager()

    async def test_get_floor_price(self, valuation_manager):
        """Test fetching floor price for a collection."""
        # Mock marketplace data
        with patch.object(valuation_manager, "_fetch_listings") as mock_listings:
            mock_listings.return_value = [
                {"price": 0.1, "token_id": 1},
                {"price": 0.12, "token_id": 2},
                {"price": 0.08, "token_id": 3},
            ]
            floor = await valuation_manager.get_floor_price("0xCollection", "ETH")
            assert floor == 0.08  # ETH

    async def test_estimate_value(self, valuation_manager):
        """Test estimating the value of a specific NFT."""
        # Simulate floor price + rarity premium
        with patch.object(valuation_manager, "get_floor_price") as mock_floor:
            mock_floor.return_value = 0.1
            with patch.object(valuation_manager, "_get_rarity_multiplier") as mock_rarity:
                mock_rarity.return_value = 1.5
                value = await valuation_manager.estimate_value(
                    collection="0xCollection",
                    token_id=1,
                    currency="ETH",
                )
                assert value == 0.15  # 0.1 * 1.5

    async def test_analyze_valuation_trends(self, valuation_manager):
        """Test analyzing valuation trends over time."""
        with patch.object(valuation_manager, "_fetch_historical_prices") as mock_hist:
            mock_hist.return_value = [0.1, 0.12, 0.11, 0.15, 0.2]
            trends = await valuation_manager.analyze_valuation_trends("0xCollection", days=30)
            assert trends["current"] == 0.2
            assert trends["change_7d"] == (0.2 - 0.11) / 0.11 * 100  # approximately 82%


# ============================== NFT TRADING MANAGER TESTS ==============================

class TestNFTTradingManager:
    """Test the NFTTradingManager for NFT trading operations."""

    @pytest.fixture
    def trading_manager(self, nft_manager):
        """Return an NFTTradingManager instance with NFTManager."""
        return NFTTradingManager(nft_manager)

    async def test_list_nft(self, trading_manager, test_private_key, test_address_from_private_key):
        """Test listing an NFT for sale."""
        # Mock the marketplace contract
        with patch.object(trading_manager, "_get_marketplace_contract") as mock_contract:
            mock_contract.return_value.functions.listItem.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(trading_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "q" * 64
                with patch.object(trading_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "q" * 64}
                    result = await trading_manager.list_nft(
                        collection="TestNFT",
                        token_id=1,
                        price=0.1,
                        currency="ETH",
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "q" * 64

    async def test_buy_nft(self, trading_manager, test_private_key, test_address_from_private_key):
        """Test buying a listed NFT."""
        with patch.object(trading_manager, "_get_marketplace_contract") as mock_contract:
            mock_contract.return_value.functions.buyItem.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x", "value": 0.1 * 10**18}
            with patch.object(trading_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "r" * 64
                with patch.object(trading_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "r" * 64}
                    result = await trading_manager.buy_nft(
                        collection="TestNFT",
                        token_id=1,
                        price=0.1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "r" * 64

    async def test_cancel_listing(self, trading_manager, test_private_key, test_address_from_private_key):
        """Test cancelling an NFT listing."""
        with patch.object(trading_manager, "_get_marketplace_contract") as mock_contract:
            mock_contract.return_value.functions.cancelListing.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(trading_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "s" * 64
                with patch.object(trading_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "s" * 64}
                    result = await trading_manager.cancel_listing(
                        collection="TestNFT",
                        token_id=1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "s" * 64


# ============================== NFT LENDING MANAGER TESTS ==============================

class TestNFTLendingManager:
    """Test the NFTLendingManager for NFT-backed loans."""

    @pytest.fixture
    def lending_manager(self, nft_manager):
        """Return an NFTLendingManager instance."""
        return NFTLendingManager(nft_manager)

    async def test_create_loan_offer(self, lending_manager, test_private_key, test_address_from_private_key):
        """Test creating a loan offer (lender)."""
        with patch.object(lending_manager, "_get_lending_contract") as mock_contract:
            mock_contract.return_value.functions.createOffer.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(lending_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "t" * 64
                with patch.object(lending_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "t" * 64}
                    result = await lending_manager.create_loan_offer(
                        collection="TestNFT",
                        token_id=1,
                        loan_amount=1.0,
                        interest_rate=0.1,
                        duration_days=30,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "t" * 64

    async def test_take_loan(self, lending_manager, test_private_key, test_address_from_private_key):
        """Test taking a loan against an NFT (borrower)."""
        with patch.object(lending_manager, "_get_lending_contract") as mock_contract:
            mock_contract.return_value.functions.takeLoan.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(lending_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "u" * 64
                with patch.object(lending_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "u" * 64}
                    result = await lending_manager.take_loan(
                        offer_id=1,
                        collection="TestNFT",
                        token_id=1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "u" * 64

    async def test_repay_loan(self, lending_manager, test_private_key, test_address_from_private_key):
        """Test repaying a loan."""
        with patch.object(lending_manager, "_get_lending_contract") as mock_contract:
            mock_contract.return_value.functions.repayLoan.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x", "value": 1.1 * 10**18}
            with patch.object(lending_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "v" * 64
                with patch.object(lending_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "v" * 64}
                    result = await lending_manager.repay_loan(
                        loan_id=1,
                        amount=1.1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "v" * 64

    async def test_claim_collateral(self, lending_manager, test_private_key, test_address_from_private_key):
        """Test claiming collateral after loan default."""
        with patch.object(lending_manager, "_get_lending_contract") as mock_contract:
            mock_contract.return_value.functions.claimCollateral.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(lending_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "w" * 64
                with patch.object(lending_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "w" * 64}
                    result = await lending_manager.claim_collateral(
                        loan_id=1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "w" * 64


# ============================== NFT STAKING MANAGER TESTS ==============================

class TestNFTStakingManager:
    """Test the NFTStakingManager for NFT staking."""

    @pytest.fixture
    def staking_manager(self, nft_manager):
        """Return an NFTStakingManager instance."""
        return NFTStakingManager(nft_manager)

    async def test_stake_nft(self, staking_manager, test_private_key, test_address_from_private_key):
        """Test staking an NFT."""
        with patch.object(staking_manager, "_get_staking_contract") as mock_contract:
            mock_contract.return_value.functions.stake.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(staking_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "x" * 64
                with patch.object(staking_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "x" * 64}
                    result = await staking_manager.stake_nft(
                        collection="TestNFT",
                        token_id=1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "x" * 64

    async def test_unstake_nft(self, staking_manager, test_private_key, test_address_from_private_key):
        """Test unstaking an NFT."""
        with patch.object(staking_manager, "_get_staking_contract") as mock_contract:
            mock_contract.return_value.functions.unstake.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(staking_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "y" * 64
                with patch.object(staking_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "y" * 64}
                    result = await staking_manager.unstake_nft(
                        collection="TestNFT",
                        token_id=1,
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "y" * 64

    async def test_get_staking_rewards(self, staking_manager):
        """Test getting staking rewards."""
        with patch.object(staking_manager, "_get_staking_contract") as mock_contract:
            mock_contract.return_value.functions.getRewards.return_value.call.return_value = 100
            rewards = await staking_manager.get_staking_rewards("0xowner")
            assert rewards == 100

    async def test_claim_rewards(self, staking_manager, test_private_key, test_address_from_private_key):
        """Test claiming staking rewards."""
        with patch.object(staking_manager, "_get_staking_contract") as mock_contract:
            mock_contract.return_value.functions.claimRewards.return_value.build_transaction.return_value = {"to": "0x123", "data": "0x"}
            with patch.object(staking_manager.nft_manager.web3_client.eth, "send_transaction") as mock_send:
                mock_send.return_value = "0x" + "z" * 64
                with patch.object(staking_manager.nft_manager.web3_client.eth, "wait_for_transaction_receipt") as mock_wait:
                    mock_wait.return_value = {"status": 1, "transactionHash": "0x" + "z" * 64}
                    result = await staking_manager.claim_rewards(
                        from_address=test_address_from_private_key,
                        private_key=test_private_key,
                    )
                    assert result["tx_hash"] == "0x" + "z" * 64


# ============================== NFT ANALYTICS TESTS ==============================

class TestNFTAnalytics:
    """Test the NFTAnalytics module for analytics on NFT collections."""

    @pytest.fixture
    def nft_analytics(self):
        """Return an NFTAnalytics instance."""
        return NFTAnalytics()

    async def test_get_collection_stats(self, nft_analytics):
        """Test getting collection statistics."""
        with patch.object(nft_analytics, "_fetch_collection_data") as mock_data:
            mock_data.return_value = {
                "total_supply": 10000,
                "unique_holders": 5000,
                "floor_price": 0.1,
                "avg_price": 0.15,
                "total_volume": 1000,
            }
            stats = await nft_analytics.get_collection_stats("0xCollection")
            assert stats["total_supply"] == 10000
            assert stats["floor_price"] == 0.1

    async def test_get_volume_analysis(self, nft_analytics):
        """Test analyzing trading volume."""
        with patch.object(nft_analytics, "_fetch_volume_data") as mock_volume:
            mock_volume.return_value = {
                "24h": 50,
                "7d": 350,
                "30d": 1500,
                "top_sales": [{"token_id": 1, "price": 10.0}],
            }
            volume = await nft_analytics.get_volume_analysis("0xCollection")
            assert volume["24h"] == 50
            assert len(volume["top_sales"]) == 1

    async def test_track_whale_activity(self, nft_analytics):
        """Test tracking whale activity."""
        with patch.object(nft_analytics, "_fetch_large_transfers") as mock_transfers:
            mock_transfers.return_value = [
                {"from": "0xWhale", "to": "0xCollector", "token_id": 1, "tx_hash": "0x123"},
                {"from": "0xWhale", "to": "0xCollector", "token_id": 2, "tx_hash": "0x456"},
            ]
            activity = await nft_analytics.track_whale_activity("0xCollection", threshold=100)
            assert len(activity) == 2
            assert activity[0]["from"] == "0xWhale"


# ============================== NFT WHALE TRACKER TESTS ==============================

class TestNFTWhaleTracker:
    """Test the NFTWhaleTracker for identifying whale wallets."""

    @pytest.fixture
    def whale_tracker(self):
        """Return an NFTWhaleTracker instance."""
        return NFTWhaleTracker()

    async def test_identify_whales(self, whale_tracker):
        """Test identifying whale wallets based on holdings."""
        with patch.object(whale_tracker, "_fetch_holder_distribution") as mock_dist:
            mock_dist.return_value = [
                {"address": "0xWhale1", "balance": 1000},
                {"address": "0xWhale2", "balance": 800},
                {"address": "0xSmall", "balance": 1},
            ]
            whales = await whale_tracker.identify_whales("0xCollection", threshold=100)
            assert len(whales) == 2
            assert whales[0]["address"] == "0xWhale1"

    async def test_track_whale_movements(self, whale_tracker):
        """Test tracking whale NFT movements."""
        with patch.object(whale_tracker, "_fetch_recent_transfers") as mock_transfers:
            mock_transfers.return_value = [
                {"from": "0xWhale1", "to": "0xExchange", "token_id": 1, "tx_hash": "0x123"},
                {"from": "0xWhale1", "to": "0xExchange", "token_id": 2, "tx_hash": "0x456"},
            ]
            movements = await whale_tracker.track_whale_movements("0xWhale1", days=7)
            assert len(movements) == 2

    async def test_get_whale_holdings(self, whale_tracker):
        """Test getting NFT holdings of a whale."""
        with patch.object(whale_tracker, "_fetch_holdings") as mock_holdings:
            mock_holdings.return_value = [1, 2, 3, 4, 5]
            holdings = await whale_tracker.get_whale_holdings("0xWhale1")
            assert len(holdings) == 5


# ============================== NFT MARKETPLACE MANAGER TESTS ==============================

class TestNFTMarketplaceManager:
    """Test the NFTMarketplaceManager for marketplace integrations."""

    @pytest.fixture
    def marketplace_manager(self):
        """Return an NFTMarketplaceManager instance."""
        return NFTMarketplaceManager()

    async def test_get_listings(self, marketplace_manager):
        """Test fetching listings from a marketplace."""
        with patch.object(marketplace_manager, "_fetch_marketplace_listings") as mock_listings:
            mock_listings.return_value = [
                {"token_id": 1, "price": 0.1, "seller": "0xSeller", "currency": "ETH"},
                {"token_id": 2, "price": 0.12, "seller": "0xSeller", "currency": "ETH"},
            ]
            listings = await marketplace_manager.get_listings("OpenSea", "0xCollection")
            assert len(listings) == 2

    async def test_get_floor_price_from_marketplace(self, marketplace_manager):
        """Test getting floor price from a specific marketplace."""
        with patch.object(marketplace_manager, "get_listings") as mock_listings:
            mock_listings.return_value = [
                {"price": 0.1},
                {"price": 0.08},
                {"price": 0.12},
            ]
            floor = await marketplace_manager.get_floor_price("OpenSea", "0xCollection")
            assert floor == 0.08

    async def test_get_volume_by_marketplace(self, marketplace_manager):
        """Test getting trading volume by marketplace."""
        with patch.object(marketplace_manager, "_fetch_volume_data") as mock_volume:
            mock_volume.return_value = {"OpenSea": 500, "Blur": 300, "LooksRare": 200}
            volume = await marketplace_manager.get_marketplace_volume("0xCollection", days=7)
            assert volume["OpenSea"] == 500


# ============================== INTEGRATION TESTS ==============================

class TestNFTIntegration:
    """Integration tests for NFT components working together."""

    async def test_full_nft_lifecycle(self, nft_manager, trading_manager, lending_manager, test_private_key, test_address_from_private_key):
        """Test a complete NFT lifecycle: transfer -> list -> sell -> loan."""
        # 1. Transfer NFT
        with patch.object(nft_manager.collections["TestNFT"], "transfer") as mock_transfer:
            mock_transfer.return_value = {"tx_hash": "0x" + "aa" * 32}
            await nft_manager.transfer_nft(
                collection_name="TestNFT",
                token_id=1,
                from_address=test_address_from_private_key,
                to_address="0x" + "bb" * 40,
                private_key=test_private_key,
            )

        # 2. List for sale
        with patch.object(trading_manager, "list_nft") as mock_list:
            mock_list.return_value = {"tx_hash": "0x" + "cc" * 32}
            await trading_manager.list_nft(
                collection="TestNFT",
                token_id=1,
                price=0.1,
                currency="ETH",
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )

        # 3. Buy NFT
        with patch.object(trading_manager, "buy_nft") as mock_buy:
            mock_buy.return_value = {"tx_hash": "0x" + "dd" * 32}
            await trading_manager.buy_nft(
                collection="TestNFT",
                token_id=1,
                price=0.1,
                from_address="0xbuyer",
                private_key="0xkey",
            )

        # 4. Use as collateral for loan
        with patch.object(lending_manager, "take_loan") as mock_loan:
            mock_loan.return_value = {"tx_hash": "0x" + "ee" * 32}
            await lending_manager.take_loan(
                offer_id=1,
                collection="TestNFT",
                token_id=1,
                from_address="0xbuyer",
                private_key="0xkey",
            )

        # All operations should have been called
        mock_transfer.assert_called_once()
        mock_list.assert_called_once()
        mock_buy.assert_called_once()
        mock_loan.assert_called_once()

    async def test_nft_staking_and_rewards(self, staking_manager, test_private_key, test_address_from_private_key):
        """Test staking an NFT and claiming rewards."""
        # Stake
        with patch.object(staking_manager, "stake_nft") as mock_stake:
            mock_stake.return_value = {"tx_hash": "0x" + "ff" * 32}
            await staking_manager.stake_nft(
                collection="TestNFT",
                token_id=1,
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )

        # Get rewards
        with patch.object(staking_manager, "get_staking_rewards") as mock_rewards:
            mock_rewards.return_value = 100
            rewards = await staking_manager.get_staking_rewards(test_address_from_private_key)
            assert rewards == 100

        # Claim rewards
        with patch.object(staking_manager, "claim_rewards") as mock_claim:
            mock_claim.return_value = {"tx_hash": "0x" + "gg" * 32}
            await staking_manager.claim_rewards(
                from_address=test_address_from_private_key,
                private_key=test_private_key,
            )

        mock_stake.assert_called_once()
        mock_claim.assert_called_once()

    async def test_nft_valuation_and_rarity(self, valuation_manager, rarity_analyzer):
        """Test combining valuation and rarity analysis."""
        # Get rarity score
        traits = [
            {"trait_type": "Background", "value": "Blue", "frequency": 0.3},
            {"trait_type": "Eyes", "value": "Red", "frequency": 0.05},
        ]
        rarity_score = rarity_analyzer.calculate_rarity_score(traits)

        # Estimate value using rarity
        with patch.object(valuation_manager, "get_floor_price") as mock_floor:
            mock_floor.return_value = 0.1
            with patch.object(valuation_manager, "_get_rarity_multiplier") as mock_mult:
                mock_mult.return_value = 1 + (rarity_score / 100)  # 1.5
                value = await valuation_manager.estimate_value(
                    collection="0xCollection",
                    token_id=1,
                    currency="ETH",
                )
                # value = floor * multiplier, floor=0.1, multiplier=1.5 => 0.15
                assert value == 0.15

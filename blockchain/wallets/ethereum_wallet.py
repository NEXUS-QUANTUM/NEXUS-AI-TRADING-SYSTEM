"""
NEXUS AI TRADING SYSTEM - ETHEREUM WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de wallet pour Ethereum et EVM-compatible blockchains.
Support complet des tokens ERC-20, ERC-721, ERC-1155, staking, DeFi, et interactions avec les smart contracts.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.eth import AsyncEth
from web3.middleware import geth_poa_middleware
from web3.contract import Contract

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    TokenInfo,
    BlockchainNetwork,
    WalletStatus,
    WalletType,
    InsufficientBalanceError,
    InvalidAddressError,
    TransactionError,
    NetworkError
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES ETHEREUM
# ============================================================================

# Tokens ERC-20 populaires sur Ethereum
ERC20_TOKENS = {
    "ETH": {
        "address": "0x0000000000000000000000000000000000000000",
        "symbol": "ETH",
        "name": "Ethereum",
        "decimals": 18
    },
    "USDT": {
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "symbol": "USDT",
        "name": "Tether USD",
        "decimals": 18
    },
    "USDC": {
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "symbol": "USDC",
        "name": "USD Coin",
        "decimals": 18
    },
    "DAI": {
        "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "symbol": "DAI",
        "name": "Dai Stablecoin",
        "decimals": 18
    },
    "WBTC": {
        "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "symbol": "WBTC",
        "name": "Wrapped Bitcoin",
        "decimals": 8
    },
    "WETH": {
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol": "WETH",
        "name": "Wrapped Ether",
        "decimals": 18
    },
    "LINK": {
        "address": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "symbol": "LINK",
        "name": "Chainlink",
        "decimals": 18
    },
    "UNI": {
        "address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "symbol": "UNI",
        "name": "Uniswap",
        "decimals": 18
    },
    "AAVE": {
        "address": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "symbol": "AAVE",
        "name": "Aave",
        "decimals": 18
    },
    "CRV": {
        "address": "0xD533a949740bb3306d119CC777fa900bA034cd52",
        "symbol": "CRV",
        "name": "Curve DAO",
        "decimals": 18
    },
    "MKR": {
        "address": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
        "symbol": "MKR",
        "name": "Maker",
        "decimals": 18
    },
    "SNX": {
        "address": "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F",
        "symbol": "SNX",
        "name": "Synthetix",
        "decimals": 18
    },
    "COMP": {
        "address": "0xc00e94Cb662C3520282E6f5717214004A7f26888",
        "symbol": "COMP",
        "name": "Compound",
        "decimals": 18
    },
    "LDO": {
        "address": "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32",
        "symbol": "LDO",
        "name": "Lido DAO",
        "decimals": 18
    },
    "RPL": {
        "address": "0xD33526068D116cE69F19A9ee46F0bd304F21A51f",
        "symbol": "RPL",
        "name": "Rocket Pool",
        "decimals": 18
    }
}

# Standard ERC-20 ABI (complet)
ERC20_ABI = [
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
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "spender", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Approval",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

# Uniswap V2 Router
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
UNISWAP_V2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

# Uniswap V3 Router
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

# Uniswap V2 Router ABI
UNISWAP_V2_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsIn",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "WETH",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# URLs des APIs Ethereum
ETHEREUM_API_URLS = {
    "mainnet": "https://api.etherscan.io/api",
    "goerli": "https://api-goerli.etherscan.io/api",
    "sepolia": "https://api-sepolia.etherscan.io/api",
    "holesky": "https://api-holesky.etherscan.io/api"
}

# RPC URLs Ethereum
ETHEREUM_RPC_URLS = {
    "mainnet": "https://eth.llamarpc.com",
    "mainnet_alt1": "https://rpc.ankr.com/eth",
    "mainnet_alt2": "https://eth-mainnet.public.blastapi.io",
    "mainnet_alt3": "https://cloudflare-eth.com",
    "goerli": "https://goerli.gateway.tenderly.co",
    "sepolia": "https://sepolia.gateway.tenderly.co",
    "holesky": "https://holesky.gateway.tenderly.co"
}


# ============================================================================
# CLASSE ETHEREUM WALLET
# ============================================================================

class EthereumWallet(BaseWallet):
    """
    Wallet pour Ethereum et EVM-compatible blockchains.
    Support complet des tokens ERC-20, ERC-721, ERC-1155, et DeFi.
    """

    def __init__(
        self,
        config: WalletConfig,
        api_keys: Optional[Dict[str, str]] = None,
        web3_provider: Optional[Web3] = None
    ):
        """
        Initialise le wallet Ethereum.

        Args:
            config: Configuration du wallet
            api_keys: Clés API pour les services externes
            web3_provider: Provider Web3 (optionnel)
        """
        super().__init__(config, api_keys, web3_provider)
        
        # Initialisation du provider Web3
        if not self.web3:
            self._init_web3()
        
        # Cache des tokens et contrats
        self._token_cache: Dict[str, TokenInfo] = {}
        self._contract_cache: Dict[str, Contract] = {}
        self._allowance_cache: Dict[str, Dict[str, Decimal]] = {}
        
        # Cache des NFT
        self._nft_cache: Dict[str, List[Dict]] = {}
        
        # Métriques
        self._metrics = {
            "transactions_count": 0,
            "total_sent": Decimal("0"),
            "total_received": Decimal("0"),
            "total_fees": Decimal("0"),
            "last_block": 0,
            "last_update": datetime.now()
        }

        logger.info(f"EthereumWallet initialisé pour {config.address[:8]}...")

    def _init_web3(self) -> None:
        """Initialise le provider Web3 pour Ethereum."""
        try:
            network = self._get_network_name(self.config.network)
            rpc_url = ETHEREUM_RPC_URLS.get(network, ETHEREUM_RPC_URLS["mainnet"])
            
            self.web3 = Web3(
                Web3.HTTPProvider(rpc_url),
                middlewares=[geth_poa_middleware]
            )
            
            if not self.web3.is_connected():
                logger.warning(f"Connexion Web3 Ethereum échouée sur {rpc_url}")
            else:
                logger.info(f"Connexion Web3 Ethereum établie sur {rpc_url}")
                
        except Exception as e:
            logger.error(f"Erreur d'initialisation Web3 Ethereum: {e}")
            raise

    async def initialize(self) -> bool:
        """
        Initialise le wallet Ethereum.

        Returns:
            True si l'initialisation a réussi
        """
        if self._is_initialized:
            return True

        try:
            # Vérification de la connexion Web3
            if not self.web3 or not self.web3.is_connected():
                self._init_web3()

            # Récupération du solde initial
            await self.get_balance()

            # Récupération du dernier bloc
            self._metrics["last_block"] = self.web3.eth.block_number

            # Récupération des tokens populaires
            for token_symbol in ["USDT", "USDC", "DAI", "WBTC", "LINK"]:
                token_info = ERC20_TOKENS.get(token_symbol)
                if token_info:
                    await self.get_token_info(token_info["address"])

            self._is_initialized = True
            logger.info(f"EthereumWallet initialisé avec succès: {self.config.address[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Erreur d'initialisation de l'EthereumWallet: {e}")
            return False

    async def get_balance(
        self,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde du wallet.

        Args:
            token_address: Adresse du token (None pour ETH)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        try:
            cache_key = token_address or "native"
            
            if not force_refresh and cache_key in self._balance_cache:
                return self._balance_cache[cache_key]

            if token_address and token_address != "0x0000000000000000000000000000000000000000":
                # Solde d'un token ERC-20
                balance = await self.get_token_balance(token_address)
                token_info = await self.get_token_info(token_address)
                
                balance_usd = balance * Decimal(str(token_info.price_usd or 0))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="ethereum",
                    network=self.config.network,
                    native_balance=Decimal("0"),
                    native_balance_usd=Decimal("0"),
                    token_balances={token_address: balance},
                    token_balances_usd={token_address: balance_usd},
                    total_balance_usd=balance_usd,
                    last_updated=datetime.now()
                )
            else:
                # Solde native ETH
                balance_wei = self.web3.eth.get_balance(self.config.address)
                balance = Decimal(str(Web3.from_wei(balance_wei, 'ether')))
                
                # Récupération du prix ETH
                eth_price = await self._get_price("ethereum")
                balance_usd = balance * Decimal(str(eth_price))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="ethereum",
                    network=self.config.network,
                    native_balance=balance,
                    native_balance_usd=balance_usd,
                    token_balances={},
                    token_balances_usd={},
                    total_balance_usd=balance_usd,
                    last_updated=datetime.now()
                )

            self._balance_cache[cache_key] = wallet_balance
            return wallet_balance

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde: {e}")
            raise NetworkError(f"Erreur de récupération du solde: {e}")

    async def get_balances(
        self,
        token_addresses: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, WalletBalance]:
        """
        Récupère les soldes de plusieurs tokens.

        Args:
            token_addresses: Liste des adresses de tokens
            force_refresh: Forcer le rafraîchissement

        Returns:
            Dictionnaire des soldes par adresse
        """
        balances = {}

        try:
            # Solde native ETH
            native_balance = await self.get_balance(force_refresh=force_refresh)
            balances["native"] = native_balance

            # Solde des tokens
            addresses = token_addresses or list(ERC20_TOKENS.values())
            for token_info in addresses:
                if isinstance(token_info, dict):
                    address = token_info.get("address")
                else:
                    address = token_info

                if address and address != "0x0000000000000000000000000000000000000000":
                    try:
                        token_balance = await self.get_balance(
                            token_address=address,
                            force_refresh=force_refresh
                        )
                        balances[address] = token_balance
                    except Exception as e:
                        logger.warning(f"Erreur lors de la récupération du solde pour {address}: {e}")

            return balances

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des soldes: {e}")
            raise NetworkError(f"Erreur de récupération des soldes: {e}")

    async def send_transaction(
        self,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        data: Optional[str] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Envoie une transaction sur Ethereum.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token (None pour ETH)
            data: Données de la transaction
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction créée
        """
        try:
            # Validation de l'adresse
            if not await self.is_valid_address(to_address):
                raise InvalidAddressError(f"Adresse invalide: {to_address}")

            # Vérification du solde
            if token_address and token_address != "0x0000000000000000000000000000000000000000":
                balance = await self.get_token_balance(token_address)
                if balance < amount:
                    raise InsufficientBalanceError(
                        f"Solde insuffisant: {balance} < {amount}"
                    )
            else:
                balance = await self.get_balance()
                if balance.native_balance < amount:
                    raise InsufficientBalanceError(
                        f"Solde ETH insuffisant: {balance.native_balance} < {amount}"
                    )

            # Estimation du gaz
            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_estimate = await self.estimate_gas(
                    to_address, amount, token_address, data
                )
                gas_limit = gas_estimate.get("gas_limit", 300000)

            # Création de la transaction
            tx = self._create_transaction(
                tx_type=TransactionType.SEND,
                to_address=to_address,
                amount=amount,
                token_address=token_address,
                metadata=metadata
            )

            # Construction de la transaction
            if token_address and token_address != "0x0000000000000000000000000000000000000000":
                # Transfert de token ERC-20
                contract = self._get_contract(token_address, ERC20_ABI)
                
                tx_data = contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    Web3.to_wei(amount, 'ether')
                ).build_transaction({
                    'from': Web3.to_checksum_address(self.config.address),
                    'gas': gas_limit,
                    'gasPrice': Web3.to_wei(gas_price, 'gwei'),
                    'nonce': self.web3.eth.get_transaction_count(
                        Web3.to_checksum_address(self.config.address)
                    )
                })
            else:
                # Transfert de ETH
                tx_data = {
                    'from': Web3.to_checksum_address(self.config.address),
                    'to': Web3.to_checksum_address(to_address),
                    'value': Web3.to_wei(amount, 'ether'),
                    'gas': gas_limit,
                    'gasPrice': Web3.to_wei(gas_price, 'gwei'),
                    'nonce': self.web3.eth.get_transaction_count(
                        Web3.to_checksum_address(self.config.address)
                    )
                }
                if data:
                    tx_data['data'] = data

            # Signature et envoi
            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data,
                self.config.private_key_encrypted
            )
            
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Mise à jour de la transaction
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING
            tx.gas_limit = gas_limit
            tx.gas_price = gas_price
            tx.timestamp = datetime.now()

            # Mise à jour des métriques
            self._metrics["transactions_count"] += 1
            self._transaction_cache[tx.tx_hash] = tx

            logger.info(f"Transaction envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la transaction: {e}")
            raise TransactionError(f"Erreur d'envoi de transaction: {e}")

    async def send_batch_transactions(
        self,
        transactions: List[Dict[str, Any]]
    ) -> List[Transaction]:
        """
        Envoie un lot de transactions.

        Args:
            transactions: Liste des transactions à envoyer

        Returns:
            Liste des transactions créées
        """
        results = []
        
        for tx_data in transactions:
            try:
                tx = await self.send_transaction(
                    to_address=tx_data.get("to_address"),
                    amount=tx_data.get("amount"),
                    token_address=tx_data.get("token_address"),
                    data=tx_data.get("data"),
                    gas_price=tx_data.get("gas_price"),
                    gas_limit=tx_data.get("gas_limit"),
                    metadata=tx_data.get("metadata")
                )
                results.append(tx)
            except Exception as e:
                logger.error(f"Erreur dans le lot de transactions: {e}")
                # Création d'une transaction échouée
                failed_tx = self._create_transaction(
                    tx_type=TransactionType.SEND,
                    to_address=tx_data.get("to_address", ""),
                    amount=tx_data.get("amount", Decimal("0")),
                    token_address=tx_data.get("token_address"),
                    metadata={"error": str(e)}
                )
                failed_tx.status = TransactionStatus.FAILED
                failed_tx.error_message = str(e)
                results.append(failed_tx)
        
        return results

    async def get_transaction(
        self,
        tx_hash: str
    ) -> Optional[Transaction]:
        """
        Récupère une transaction par son hash.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Transaction ou None
        """
        try:
            # Vérification du cache
            if tx_hash in self._transaction_cache:
                tx = self._transaction_cache[tx_hash]
                # Mise à jour du statut
                if tx.status == TransactionStatus.PENDING:
                    await self._update_transaction_status(tx)
                return tx

            # Récupération depuis l'API Etherscan
            api_key = await self._get_api_key("etherscan")
            if api_key:
                tx_data = await self._get_transaction_from_api(tx_hash, api_key)
                if tx_data:
                    tx = self._parse_transaction_from_api(tx_data)
                    self._transaction_cache[tx_hash] = tx
                    return tx

            # Récupération via Web3
            tx_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            if tx_receipt:
                tx = self._parse_transaction_from_receipt(tx_receipt)
                self._transaction_cache[tx_hash] = tx
                return tx

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la transaction: {e}")
            return None

    async def get_transactions(
        self,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Récupère l'historique des transactions.

        Args:
            from_block: Bloc de début
            to_block: Bloc de fin
            limit: Nombre de transactions
            offset: Décalage

        Returns:
            Liste des transactions
        """
        transactions = []

        try:
            # Utilisation de l'API Etherscan
            api_key = await self._get_api_key("etherscan")
            if api_key:
                tx_list = await self._get_transactions_from_api(
                    from_block, to_block, limit, offset, api_key
                )
                for tx_data in tx_list:
                    tx = self._parse_transaction_from_api(tx_data)
                    transactions.append(tx)

            return transactions

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des transactions: {e}")
            return []

    async def estimate_gas(
        self,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estime les frais de gaz pour une transaction.

        Args:
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token
            data: Données de la transaction

        Returns:
            Estimation des frais
        """
        try:
            if token_address and token_address != "0x0000000000000000000000000000000000000000":
                # Transfert de token ERC-20
                contract = self._get_contract(token_address, ERC20_ABI)
                
                gas_estimate = contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    Web3.to_wei(amount, 'ether')
                ).estimate_gas({
                    'from': Web3.to_checksum_address(self.config.address)
                })
            else:
                # Transfert de ETH
                gas_estimate = self.web3.eth.estimate_gas({
                    'from': Web3.to_checksum_address(self.config.address),
                    'to': Web3.to_checksum_address(to_address),
                    'value': Web3.to_wei(amount, 'ether'),
                    'data': data or '0x'
                })

            gas_price = await self.get_gas_price()
            gas_cost = Decimal(str(gas_estimate)) * gas_price

            return {
                "gas_limit": gas_estimate,
                "gas_price": float(gas_price),
                "gas_cost": float(gas_cost),
                "gas_cost_usd": float(gas_cost * Decimal(str(await self._get_price("ethereum")))),
                "token_address": token_address
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation du gaz: {e}")
            return {
                "gas_limit": 300000,
                "gas_price": 30.0,
                "gas_cost": 0.009,
                "gas_cost_usd": 25.0,
                "error": str(e)
            }

    async def get_gas_price(self) -> Decimal:
        """
        Récupère le prix actuel du gaz sur Ethereum.

        Returns:
            Prix du gaz en GWEI
        """
        try:
            gas_price_wei = self.web3.eth.gas_price
            return Decimal(str(Web3.from_wei(gas_price_wei, 'gwei')))
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix du gaz: {e}")
            return Decimal("30.0")

    async def get_network_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du réseau Ethereum.

        Returns:
            Statut du réseau
        """
        try:
            block_number = self.web3.eth.block_number
            gas_price = await self.get_gas_price()
            chain_id = self.web3.eth.chain_id

            return {
                "network": "ethereum",
                "chain_id": chain_id,
                "block_number": block_number,
                "gas_price": float(gas_price),
                "is_connected": self.web3.is_connected(),
                "last_update": datetime.now().isoformat(),
                "node_url": self.web3.provider.endpoint_uri
            }
        except Exception as e:
            return {
                "network": "ethereum",
                "error": str(e),
                "is_connected": False,
                "last_update": datetime.now().isoformat()
            }

    async def is_valid_address(self, address: str) -> bool:
        """
        Vérifie si une adresse Ethereum est valide.

        Args:
            address: Adresse à vérifier

        Returns:
            True si l'adresse est valide
        """
        try:
            return Web3.is_address(address) and Web3.is_checksum_address(address)
        except Exception:
            return False

    async def get_token_info(
        self,
        token_address: str
    ) -> Optional[TokenInfo]:
        """
        Récupère les informations d'un token ERC-20.

        Args:
            token_address: Adresse du token

        Returns:
            Informations du token
        """
        try:
            # Vérification du cache
            if token_address in self._token_cache:
                return self._token_cache[token_address]

            # Vérification des tokens prédéfinis
            for token_data in ERC20_TOKENS.values():
                if token_data["address"].lower() == token_address.lower():
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=token_data["symbol"],
                        name=token_data["name"],
                        decimals=token_data["decimals"],
                        blockchain="ethereum",
                        network=self.config.network
                    )
                    self._token_cache[token_address] = token_info
                    return token_info

            # Récupération via le contrat
            contract = self._get_contract(token_address, ERC20_ABI)

            try:
                symbol = contract.functions.symbol().call()
                name = contract.functions.name().call()
                decimals = contract.functions.decimals().call()

                token_info = TokenInfo(
                    address=token_address,
                    symbol=symbol,
                    name=name,
                    decimals=decimals,
                    blockchain="ethereum",
                    network=self.config.network
                )

                # Récupération du prix via CoinGecko
                price = await self._get_price(symbol.lower())
                token_info.price_usd = price

                self._token_cache[token_address] = token_info
                return token_info

            except Exception as e:
                logger.error(f"Erreur lors de la récupération des infos du token: {e}")
                return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos du token: {e}")
            return None

    async def get_token_balance(
        self,
        token_address: str,
        address: Optional[str] = None
    ) -> Decimal:
        """
        Récupère le solde d'un token ERC-20.

        Args:
            token_address: Adresse du token
            address: Adresse du wallet (optionnel)

        Returns:
            Solde du token
        """
        try:
            addr = address or self.config.address
            contract = self._get_contract(token_address, ERC20_ABI)

            balance = contract.functions.balanceOf(
                Web3.to_checksum_address(addr)
            ).call()

            token_info = await self.get_token_info(token_address)
            if token_info:
                return Decimal(str(balance)) / Decimal(str(10 ** token_info.decimals))
            
            return Decimal(str(Web3.from_wei(balance, 'ether')))

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde du token: {e}")
            return Decimal("0")

    async def approve_token(
        self,
        token_address: str,
        spender_address: str,
        amount: Decimal,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Approuve un spender pour un token ERC-20.

        Args:
            token_address: Adresse du token
            spender_address: Adresse du spender
            amount: Montant à approuver
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction d'approbation
        """
        try:
            contract = self._get_contract(token_address, ERC20_ABI)

            tx_data = contract.functions.approve(
                Web3.to_checksum_address(spender_address),
                Web3.to_wei(amount, 'ether')
            ).build_transaction({
                'from': Web3.to_checksum_address(self.config.address),
                'gas': 200000,
                'gasPrice': Web3.to_wei(await self.get_gas_price(), 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(self.config.address)
                )
            })

            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data,
                self.config.private_key_encrypted
            )

            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx = self._create_transaction(
                tx_type=TransactionType.APPROVAL,
                to_address=spender_address,
                amount=amount,
                token_address=token_address,
                metadata=metadata or {}
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Approbation de token envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors de l'approbation du token: {e}")
            raise TransactionError(f"Erreur d'approbation: {e}")

    async def get_allowance(
        self,
        token_address: str,
        owner_address: str,
        spender_address: str
    ) -> Decimal:
        """
        Récupère l'allowance d'un spender.

        Args:
            token_address: Adresse du token
            owner_address: Adresse du propriétaire
            spender_address: Adresse du spender

        Returns:
            Allowance du spender
        """
        try:
            cache_key = f"{token_address}:{owner_address}:{spender_address}"
            if cache_key in self._allowance_cache:
                return self._allowance_cache[cache_key]

            contract = self._get_contract(token_address, ERC20_ABI)

            allowance = contract.functions.allowance(
                Web3.to_checksum_address(owner_address),
                Web3.to_checksum_address(spender_address)
            ).call()

            token_info = await self.get_token_info(token_address)
            if token_info:
                result = Decimal(str(allowance)) / Decimal(str(10 ** token_info.decimals))
            else:
                result = Decimal(str(Web3.from_wei(allowance, 'ether')))

            self._allowance_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'allowance: {e}")
            return Decimal("0")

    async def sign_message(
        self,
        message: str,
        address: Optional[str] = None
    ) -> str:
        """
        Signe un message.

        Args:
            message: Message à signer
            address: Adresse à utiliser (optionnel)

        Returns:
            Signature du message
        """
        try:
            msg_hash = encode_defunct(text=message)
            signature = self.web3.eth.account.sign_message(
                msg_hash,
                self.config.private_key_encrypted
            )
            return signature.signature.hex()
        except Exception as e:
            logger.error(f"Erreur lors de la signature du message: {e}")
            raise

    async def verify_signature(
        self,
        message: str,
        signature: str,
        address: str
    ) -> bool:
        """
        Vérifie une signature.

        Args:
            message: Message signé
            signature: Signature à vérifier
            address: Adresse qui a signé

        Returns:
            True si la signature est valide
        """
        try:
            msg_hash = encode_defunct(text=message)
            recovered_address = self.web3.eth.account.recover_message(
                msg_hash,
                signature=signature
            )
            return recovered_address.lower() == address.lower()
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la signature: {e}")
            return False

    async def get_transaction_count(
        self,
        address: Optional[str] = None
    ) -> int:
        """
        Récupère le nombre de transactions d'une adresse.

        Args:
            address: Adresse à vérifier (optionnel)

        Returns:
            Nombre de transactions
        """
        try:
            addr = address or self.config.address
            return self.web3.eth.get_transaction_count(
                Web3.to_checksum_address(addr)
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du nombre de transactions: {e}")
            return 0

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du wallet et de la connexion.

        Returns:
            État de santé du wallet
        """
        try:
            network_status = await self.get_network_status()
            
            return {
                "status": "healthy" if network_status["is_connected"] else "unhealthy",
                "wallet_id": str(self.config.wallet_id),
                "address": self.config.address[:8] + "..." + self.config.address[-8:],
                "network": network_status,
                "transactions_count": self._metrics["transactions_count"],
                "last_update": self._metrics["last_update"].isoformat(),
                "is_initialized": self._is_initialized,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "wallet_id": str(self.config.wallet_id),
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    # ========================================================================
    # MÉTHODES SPÉCIFIQUES ETHEREUM
    # ========================================================================

    async def swap_eth_for_tokens(
        self,
        token_address: str,
        amount_eth: Decimal,
        amount_out_min: Optional[Decimal] = None,
        deadline: Optional[int] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Échange ETH contre des tokens via Uniswap.

        Args:
            token_address: Adresse du token à acheter
            amount_eth: Montant d'ETH à échanger
            amount_out_min: Montant minimum de tokens à recevoir
            deadline: Deadline de la transaction
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)

        Returns:
            Transaction d'échange
        """
        try:
            # Estimation du montant minimum
            if not amount_out_min:
                router = self._get_contract(UNISWAP_V2_ROUTER, UNISWAP_V2_ROUTER_ABI)
                weth_address = router.functions.WETH().call()
                
                amounts = router.functions.getAmountsOut(
                    Web3.to_wei(amount_eth, 'ether'),
                    [weth_address, Web3.to_checksum_address(token_address)]
                ).call()
                amount_out_min = Decimal(str(Web3.from_wei(amounts[-1], 'ether'))) * Decimal("0.95")

            if not deadline:
                deadline = int(datetime.now().timestamp()) + 3600

            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_limit = 300000

            # Construction de la transaction
            router = self._get_contract(UNISWAP_V2_ROUTER, UNISWAP_V2_ROUTER_ABI)
            weth_address = router.functions.WETH().call()

            tx_data = router.functions.swapExactETHForTokens(
                Web3.to_wei(amount_out_min, 'ether'),
                [weth_address, Web3.to_checksum_address(token_address)],
                Web3.to_checksum_address(self.config.address),
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(self.config.address),
                'value': Web3.to_wei(amount_eth, 'ether'),
                'gas': gas_limit,
                'gasPrice': Web3.to_wei(gas_price, 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(self.config.address)
                )
            })

            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data,
                self.config.private_key_encrypted
            )

            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx = self._create_transaction(
                tx_type=TransactionType.SWAP,
                to_address=token_address,
                amount=amount_eth,
                token_address=token_address,
                metadata={
                    "swap_type": "eth_to_tokens",
                    "amount_out_min": float(amount_out_min),
                    "deadline": deadline
                }
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Swap ETH -> Token envoyé: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du swap ETH -> Token: {e}")
            raise TransactionError(f"Erreur de swap: {e}")

    async def swap_tokens_for_eth(
        self,
        token_address: str,
        amount_token: Decimal,
        amount_out_min: Optional[Decimal] = None,
        deadline: Optional[int] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Échange des tokens contre ETH via Uniswap.

        Args:
            token_address: Adresse du token à vendre
            amount_token: Montant de tokens à échanger
            amount_out_min: Montant minimum d'ETH à recevoir
            deadline: Deadline de la transaction
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)

        Returns:
            Transaction d'échange
        """
        try:
            # Vérification du solde
            balance = await self.get_token_balance(token_address)
            if balance < amount_token:
                raise InsufficientBalanceError(
                    f"Solde insuffisant: {balance} < {amount_token}"
                )

            # Vérification de l'allowance
            allowance = await self.get_allowance(
                token_address,
                self.config.address,
                UNISWAP_V2_ROUTER
            )
            if allowance < amount_token:
                # Approbation du token
                await self.approve_token(
                    token_address,
                    UNISWAP_V2_ROUTER,
                    amount_token
                )

            # Estimation du montant minimum
            if not amount_out_min:
                router = self._get_contract(UNISWAP_V2_ROUTER, UNISWAP_V2_ROUTER_ABI)
                weth_address = router.functions.WETH().call()
                
                amounts = router.functions.getAmountsOut(
                    Web3.to_wei(amount_token, 'ether'),
                    [Web3.to_checksum_address(token_address), weth_address]
                ).call()
                amount_out_min = Decimal(str(Web3.from_wei(amounts[-1], 'ether'))) * Decimal("0.95")

            if not deadline:
                deadline = int(datetime.now().timestamp()) + 3600

            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_limit = 300000

            # Construction de la transaction
            router = self._get_contract(UNISWAP_V2_ROUTER, UNISWAP_V2_ROUTER_ABI)
            weth_address = router.functions.WETH().call()

            tx_data = router.functions.swapExactTokensForETH(
                Web3.to_wei(amount_token, 'ether'),
                Web3.to_wei(amount_out_min, 'ether'),
                [Web3.to_checksum_address(token_address), weth_address],
                Web3.to_checksum_address(self.config.address),
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(self.config.address),
                'gas': gas_limit,
                'gasPrice': Web3.to_wei(gas_price, 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(self.config.address)
                )
            })

            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data,
                self.config.private_key_encrypted
            )

            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx = self._create_transaction(
                tx_type=TransactionType.SWAP,
                to_address=token_address,
                amount=amount_token,
                token_address=token_address,
                metadata={
                    "swap_type": "tokens_to_eth",
                    "amount_out_min": float(amount_out_min),
                    "deadline": deadline
                }
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Swap Token -> ETH envoyé: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du swap Token -> ETH: {e}")
            raise TransactionError(f"Erreur de swap: {e}")

    async def deploy_contract(
        self,
        bytecode: str,
        abi: List[Dict],
        constructor_args: Optional[List[Any]] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Déploie un smart contract.

        Args:
            bytecode: Bytecode du contrat
            abi: ABI du contrat
            constructor_args: Arguments du constructeur
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)

        Returns:
            Transaction de déploiement
        """
        try:
            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_limit = 1000000

            # Construction du contrat
            contract = self.web3.eth.contract(abi=abi, bytecode=bytecode)
            
            # Construction de la transaction de déploiement
            tx_data = contract.constructor(*constructor_args).build_transaction({
                'from': Web3.to_checksum_address(self.config.address),
                'gas': gas_limit,
                'gasPrice': Web3.to_wei(gas_price, 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(self.config.address)
                )
            })

            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data,
                self.config.private_key_encrypted
            )

            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx = self._create_transaction(
                tx_type=TransactionType.DEPLOY,
                to_address="",
                amount=Decimal("0"),
                metadata={
                    "bytecode": bytecode[:100] + "...",
                    "constructor_args": constructor_args,
                    "contract_address": None  # Sera mis à jour après le déploiement
                }
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Déploiement de contrat envoyé: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du déploiement du contrat: {e}")
            raise TransactionError(f"Erreur de déploiement: {e}")

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    def _get_contract(
        self,
        address: str,
        abi: List[Dict]
    ) -> Contract:
        """
        Récupère ou crée un contrat Web3.

        Args:
            address: Adresse du contrat
            abi: ABI du contrat

        Returns:
            Instance du contrat
        """
        checksum_address = Web3.to_checksum_address(address)
        
        if checksum_address not in self._contract_cache:
            self._contract_cache[checksum_address] = self.web3.eth.contract(
                address=checksum_address,
                abi=abi
            )
        
        return self._contract_cache[checksum_address]

    def _create_transaction(
        self,
        tx_type: TransactionType,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Crée une transaction.

        Args:
            tx_type: Type de transaction
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token
            metadata: Métadonnées

        Returns:
            Transaction créée
        """
        return Transaction(
            tx_id=uuid4(),
            wallet_id=self.config.wallet_id,
            user_id=self.config.user_id,
            blockchain="ethereum",
            network=self.config.network,
            tx_type=tx_type,
            from_address=self.config.address,
            to_address=to_address,
            amount=amount,
            amount_usd=amount * Decimal(str(await self._get_price("ethereum"))),
            token_address=token_address,
            token_symbol=ERC20_TOKENS.get(token_address, {}).get("symbol") if token_address else None,
            gas_currency="ETH",
            status=TransactionStatus.PENDING,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

    async def _update_transaction_status(self, tx: Transaction) -> None:
        """
        Met à jour le statut d'une transaction.

        Args:
            tx: Transaction à mettre à jour
        """
        try:
            receipt = self.web3.eth.get_transaction_receipt(tx.tx_hash)
            
            if receipt:
                tx.block_number = receipt.get("blockNumber")
                tx.block_hash = receipt.get("blockHash").hex() if receipt.get("blockHash") else None
                tx.gas_used = receipt.get("gasUsed")
                tx.confirmations = self.web3.eth.block_number - tx.block_number if tx.block_number else 0
                
                if receipt.get("status") == 1:
                    tx.status = TransactionStatus.CONFIRMED
                    tx.completed_at = datetime.now()
                else:
                    tx.status = TransactionStatus.FAILED
                    tx.error_message = "Transaction échouée"
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")

    async def _get_transaction_from_api(
        self,
        tx_hash: str,
        api_key: str
    ) -> Optional[Dict]:
        """
        Récupère une transaction via l'API Etherscan.

        Args:
            tx_hash: Hash de la transaction
            api_key: Clé API Etherscan

        Returns:
            Données de la transaction
        """
        try:
            network = self._get_network_name(self.config.network)
            url = ETHEREUM_API_URLS.get(network, ETHEREUM_API_URLS["mainnet"])
            
            data = await self._make_request(
                method="GET",
                url=url,
                params={
                    "module": "transaction",
                    "action": "gettxreceiptstatus",
                    "txhash": tx_hash,
                    "apikey": api_key
                }
            )
            
            if data.get("status") == "1":
                return data.get("result")
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la transaction: {e}")
            return None

    async def _get_transactions_from_api(
        self,
        from_block: Optional[int],
        to_block: Optional[int],
        limit: int,
        offset: int,
        api_key: str
    ) -> List[Dict]:
        """
        Récupère les transactions via l'API Etherscan.

        Args:
            from_block: Bloc de début
            to_block: Bloc de fin
            limit: Nombre de transactions
            offset: Décalage
            api_key: Clé API Etherscan

        Returns:
            Liste des transactions
        """
        try:
            network = self._get_network_name(self.config.network)
            url = ETHEREUM_API_URLS.get(network, ETHEREUM_API_URLS["mainnet"])
            
            params = {
                "module": "account",
                "action": "txlist",
                "address": self.config.address,
                "startblock": from_block or 0,
                "endblock": to_block or 99999999,
                "sort": "desc",
                "offset": limit,
                "apikey": api_key
            }
            
            data = await self._make_request("GET", url, params=params)
            
            if data.get("status") == "1":
                return data.get("result", [])
            return []

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des transactions: {e}")
            return []

    def _parse_transaction_from_api(self, tx_data: Dict) -> Transaction:
        """
        Parse une transaction depuis les données API.

        Args:
            tx_data: Données de la transaction

        Returns:
            Transaction parsée
        """
        is_receive = tx_data.get("to", "").lower() == self.config.address.lower()
        
        return Transaction(
            tx_id=uuid4(),
            wallet_id=self.config.wallet_id,
            user_id=self.config.user_id,
            blockchain="ethereum",
            network=self.config.network,
            tx_type=TransactionType.RECEIVE if is_receive else TransactionType.SEND,
            from_address=tx_data.get("from", ""),
            to_address=tx_data.get("to", ""),
            amount=Decimal(str(int(tx_data.get("value", 0)) / 10**18)),
            amount_usd=Decimal("0"),
            tx_hash=tx_data.get("hash"),
            block_number=int(tx_data.get("blockNumber", 0)),
            gas_used=int(tx_data.get("gasUsed", 0)),
            gas_price=Decimal(str(int(tx_data.get("gasPrice", 0)) / 10**9)),
            gas_currency="ETH",
            status=TransactionStatus.CONFIRMED if tx_data.get("txreceipt_status") == "1" else TransactionStatus.FAILED,
            timestamp=datetime.fromtimestamp(int(tx_data.get("timeStamp", 0))),
            completed_at=datetime.fromtimestamp(int(tx_data.get("timeStamp", 0))),
            metadata={
                "contract_address": tx_data.get("contractAddress"),
                "confirmations": int(tx_data.get("confirmations", 0))
            }
        )

    def _parse_transaction_from_receipt(self, receipt: Any) -> Transaction:
        """
        Parse une transaction depuis un receipt Web3.

        Args:
            receipt: Receipt Web3

        Returns:
            Transaction parsée
        """
        return Transaction(
            tx_id=uuid4(),
            wallet_id=self.config.wallet_id,
            user_id=self.config.user_id,
            blockchain="ethereum",
            network=self.config.network,
            tx_type=TransactionType.SEND,
            from_address=receipt.get("from", ""),
            to_address=receipt.get("to", ""),
            amount=Decimal("0"),
            amount_usd=Decimal("0"),
            tx_hash=receipt.get("transactionHash").hex() if receipt.get("transactionHash") else "",
            block_number=receipt.get("blockNumber"),
            block_hash=receipt.get("blockHash").hex() if receipt.get("blockHash") else "",
            gas_used=receipt.get("gasUsed"),
            gas_currency="ETH",
            status=TransactionStatus.CONFIRMED if receipt.get("status") == 1 else TransactionStatus.FAILED,
            timestamp=datetime.now()
        )


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_ethereum_wallet(
    user_id: UUID,
    name: str = "Ethereum Wallet",
    network: BlockchainNetwork = BlockchainNetwork.ETHEREUM_MAINNET,
    private_key: Optional[str] = None,
    mnemonic: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> EthereumWallet:
    """
    Crée un wallet Ethereum.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du wallet
        network: Réseau Ethereum
        private_key: Clé privée (optionnel)
        mnemonic: Phrase mnémonique (optionnel)
        api_keys: Clés API

    Returns:
        Wallet Ethereum créé
    """
    from eth_account import Account
    
    if private_key:
        account = Account.from_key(private_key)
        address = account.address
    elif mnemonic:
        Account.enable_unaudited_hdwallet_features()
        account = Account.from_mnemonic(mnemonic)
        address = account.address
        private_key = account.key.hex()
    else:
        # Génération d'un nouveau wallet
        account = Account.create()
        address = account.address
        private_key = account.key.hex()

    config = WalletConfig(
        wallet_id=uuid4(),
        user_id=user_id,
        name=name,
        type=WalletType.EOA,
        blockchain="ethereum",
        network=network,
        address=address,
        private_key_encrypted=private_key,  # À chiffrer en production
        public_key=account.key.hex(),
        is_created=True,
        is_imported=bool(private_key or mnemonic),
        is_hardware=False,
        status=WalletStatus.ACTIVE,
        metadata={"source": "nexus_ethereum_wallet"}
    )

    return EthereumWallet(config, api_keys)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "EthereumWallet",
    "ERC20_TOKENS",
    "UNISWAP_V2_ROUTER",
    "UNISWAP_V2_FACTORY",
    "UNISWAP_V3_ROUTER",
    "UNISWAP_V3_FACTORY",
    "UNISWAP_V2_ROUTER_ABI",
    "ERC20_ABI",
    "create_ethereum_wallet"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du wallet Ethereum."""
    print("=" * 60)
    print("NEXUS AI TRADING - ETHEREUM WALLET MODULE")
    print("=" * 60)

    # Création d'un wallet
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Main Ethereum Wallet",
        network=BlockchainNetwork.ETHEREUM_MAINNET,
        api_keys={"etherscan": "YOUR_ETHERSCAN_API_KEY"}
    )

    # Initialisation
    await wallet.initialize()
    
    print(f"\n✅ Wallet Ethereum créé:")
    print(f"   ID: {wallet.config.wallet_id}")
    print(f"   Nom: {wallet.config.name}")
    print(f"   Adresse: {wallet.config.address}")

    # Récupération du solde
    balance = await wallet.get_balance()
    print(f"\n💰 Solde ETH: {balance.native_balance} ETH (${balance.native_balance_usd:.2f})")

    # Récupération du solde d'un token
    usdt_balance = await wallet.get_token_balance(ERC20_TOKENS["USDT"]["address"])
    print(f"💰 Solde USDT: {usdt_balance} USDT")

    # Vérification du réseau
    network_status = await wallet.get_network_status()
    print(f"\n🌐 Statut du réseau:")
    print(f"   Block: {network_status.get('block_number')}")
    print(f"   Gaz: {network_status.get('gas_price')} GWEI")
    print(f"   Connecté: {network_status.get('is_connected')}")

    # Santé du wallet
    health = await wallet.get_health()
    print(f"\n❤️ Santé: {health['status']}")

    print("\n" + "=" * 60)
    print("EthereumWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

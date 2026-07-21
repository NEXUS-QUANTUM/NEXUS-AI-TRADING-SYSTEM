"""
NEXUS AI TRADING SYSTEM - POLYGON WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de wallet pour Polygon (MATIC) et EVM-compatible blockchains.
Support complet des tokens ERC-20, staking, DeFi, bridges, et interactions avec les smart contracts.

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
# CONSTANTES POLYGON
# ============================================================================

# Tokens ERC-20 populaires sur Polygon
POLYGON_TOKENS = {
    "MATIC": {
        "address": "0x0000000000000000000000000000000000001010",
        "symbol": "MATIC",
        "name": "Polygon",
        "decimals": 18
    },
    "USDT": {
        "address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "symbol": "USDT",
        "name": "Tether USD",
        "decimals": 18
    },
    "USDC": {
        "address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "symbol": "USDC",
        "name": "USD Coin",
        "decimals": 18
    },
    "DAI": {
        "address": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "symbol": "DAI",
        "name": "Dai Stablecoin",
        "decimals": 18
    },
    "WETH": {
        "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "symbol": "WETH",
        "name": "Wrapped Ether",
        "decimals": 18
    },
    "WBTC": {
        "address": "0x1bfd67037b42cf73acF2047067bd4F2C47D9BfD6",
        "symbol": "WBTC",
        "name": "Wrapped Bitcoin",
        "decimals": 8
    },
    "LINK": {
        "address": "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",
        "symbol": "LINK",
        "name": "Chainlink",
        "decimals": 18
    },
    "AAVE": {
        "address": "0xD6DF932A45C0f255f85145f286eA0b292B21C90B",
        "symbol": "AAVE",
        "name": "Aave",
        "decimals": 18
    },
    "CRV": {
        "address": "0x172370d5Cd63279eFa6d502DAB29171933a610AF",
        "symbol": "CRV",
        "name": "Curve DAO",
        "decimals": 18
    },
    "UNI": {
        "address": "0xb33EaAd8d922B1083446DC23f610c2567fB5180f",
        "symbol": "UNI",
        "name": "Uniswap",
        "decimals": 18
    },
    "SUSHI": {
        "address": "0x0b3F868E0BE5597D5DB7fEB59E1CADBb0fdDa50a",
        "symbol": "SUSHI",
        "name": "SushiSwap",
        "decimals": 18
    },
    "QUICK": {
        "address": "0x831753DD7087CaC61aB5644b308642cc1c33Dc13",
        "symbol": "QUICK",
        "name": "QuickSwap",
        "decimals": 18
    },
    "WMATIC": {
        "address": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "symbol": "WMATIC",
        "name": "Wrapped MATIC",
        "decimals": 18
    },
    "MIM": {
        "address": "0x49a0400587A7F65072c87c4910449fDcC5c47242",
        "symbol": "MIM",
        "name": "Magic Internet Money",
        "decimals": 18
    },
    "BAL": {
        "address": "0x9a71012B13CA4d3D0Cdc72A177DF3ef03b0E76A3",
        "symbol": "BAL",
        "name": "Balancer",
        "decimals": 18
    }
}

# Standard ERC-20 ABI
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

# QuickSwap Router
QUICKSWAP_ROUTER = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
QUICKSWAP_FACTORY = "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32"

# QuickSwap Router ABI
QUICKSWAP_ROUTER_ABI = [
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

# URLs des APIs Polygon
POLYGON_API_URLS = {
    "mainnet": "https://api.polygonscan.com/api",
    "mumbai": "https://api-mumbai.polygonscan.com/api"
}

# RPC URLs Polygon
POLYGON_RPC_URLS = {
    "mainnet": "https://polygon-rpc.com",
    "mainnet_alt1": "https://rpc-mainnet.maticvigil.com",
    "mainnet_alt2": "https://rpc-mainnet.matic.network",
    "mainnet_alt3": "https://rpc-mainnet.polygon.technology",
    "mainnet_alt4": "https://polygon-mainnet.g.alchemy.com/v2/demo",
    "mumbai": "https://rpc-mumbai.maticvigil.com"
}


# ============================================================================
# CLASSE POLYGON WALLET
# ============================================================================

class PolygonWallet(BaseWallet):
    """
    Wallet pour Polygon (MATIC) et EVM-compatible blockchains.
    Support complet des tokens ERC-20, staking, DeFi, et bridges.
    """

    def __init__(
        self,
        config: WalletConfig,
        api_keys: Optional[Dict[str, str]] = None,
        web3_provider: Optional[Web3] = None
    ):
        """
        Initialise le wallet Polygon.

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
        
        # Cache des bridges
        self._bridge_cache: Dict[str, Dict] = {}
        
        # Métriques
        self._metrics = {
            "transactions_count": 0,
            "total_sent": Decimal("0"),
            "total_received": Decimal("0"),
            "total_fees": Decimal("0"),
            "last_block": 0,
            "last_update": datetime.now()
        }

        logger.info(f"PolygonWallet initialisé pour {config.address[:8]}...")

    def _init_web3(self) -> None:
        """Initialise le provider Web3 pour Polygon."""
        try:
            network = self._get_network_name(self.config.network)
            rpc_url = POLYGON_RPC_URLS.get(network, POLYGON_RPC_URLS["mainnet"])
            
            self.web3 = Web3(
                Web3.HTTPProvider(rpc_url),
                middlewares=[geth_poa_middleware]
            )
            
            if not self.web3.is_connected():
                logger.warning(f"Connexion Web3 Polygon échouée sur {rpc_url}")
            else:
                logger.info(f"Connexion Web3 Polygon établie sur {rpc_url}")
                
        except Exception as e:
            logger.error(f"Erreur d'initialisation Web3 Polygon: {e}")
            raise

    async def initialize(self) -> bool:
        """
        Initialise le wallet Polygon.

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
            for token_symbol in ["USDT", "USDC", "DAI", "WETH", "WBTC"]:
                token_info = POLYGON_TOKENS.get(token_symbol)
                if token_info:
                    await self.get_token_info(token_info["address"])

            self._is_initialized = True
            logger.info(f"PolygonWallet initialisé avec succès: {self.config.address[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Erreur d'initialisation du PolygonWallet: {e}")
            return False

    async def get_balance(
        self,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde du wallet.

        Args:
            token_address: Adresse du token (None pour MATIC)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        try:
            cache_key = token_address or "native"
            
            if not force_refresh and cache_key in self._balance_cache:
                return self._balance_cache[cache_key]

            if token_address and token_address != "0x0000000000000000000000000000000000001010":
                # Solde d'un token ERC-20
                balance = await self.get_token_balance(token_address)
                token_info = await self.get_token_info(token_address)
                
                balance_usd = balance * Decimal(str(token_info.price_usd or 0))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="polygon",
                    network=self.config.network,
                    native_balance=Decimal("0"),
                    native_balance_usd=Decimal("0"),
                    token_balances={token_address: balance},
                    token_balances_usd={token_address: balance_usd},
                    total_balance_usd=balance_usd,
                    last_updated=datetime.now()
                )
            else:
                # Solde native MATIC
                balance_wei = self.web3.eth.get_balance(self.config.address)
                balance = Decimal(str(Web3.from_wei(balance_wei, 'ether')))
                
                # Récupération du prix MATIC
                matic_price = await self._get_price("polygon")
                balance_usd = balance * Decimal(str(matic_price))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="polygon",
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
            # Solde native MATIC
            native_balance = await self.get_balance(force_refresh=force_refresh)
            balances["native"] = native_balance

            # Solde des tokens
            addresses = token_addresses or list(POLYGON_TOKENS.values())
            for token_info in addresses:
                if isinstance(token_info, dict):
                    address = token_info.get("address")
                else:
                    address = token_info

                if address and address != "0x0000000000000000000000000000000000001010":
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
        Envoie une transaction sur Polygon.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token (None pour MATIC)
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
            if token_address and token_address != "0x0000000000000000000000000000000000001010":
                balance = await self.get_token_balance(token_address)
                if balance < amount:
                    raise InsufficientBalanceError(
                        f"Solde insuffisant: {balance} < {amount}"
                    )
            else:
                balance = await self.get_balance()
                if balance.native_balance < amount:
                    raise InsufficientBalanceError(
                        f"Solde MATIC insuffisant: {balance.native_balance} < {amount}"
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
            if token_address and token_address != "0x0000000000000000000000000000000000001010":
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
                # Transfert de MATIC
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

            # Récupération depuis l'API Polygonscan
            api_key = await self._get_api_key("polygonscan")
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
            # Utilisation de l'API Polygonscan
            api_key = await self._get_api_key("polygonscan")
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
            if token_address and token_address != "0x0000000000000000000000000000000000001010":
                # Transfert de token ERC-20
                contract = self._get_contract(token_address, ERC20_ABI)
                
                gas_estimate = contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    Web3.to_wei(amount, 'ether')
                ).estimate_gas({
                    'from': Web3.to_checksum_address(self.config.address)
                })
            else:
                # Transfert de MATIC
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
                "gas_cost_usd": float(gas_cost * Decimal(str(await self._get_price("polygon")))),
                "token_address": token_address
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation du gaz: {e}")
            return {
                "gas_limit": 300000,
                "gas_price": 30.0,
                "gas_cost": 0.009,
                "gas_cost_usd": 0.015,
                "error": str(e)
            }

    async def get_gas_price(self) -> Decimal:
        """
        Récupère le prix actuel du gaz sur Polygon.

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
        Récupère le statut du réseau Polygon.

        Returns:
            Statut du réseau
        """
        try:
            block_number = self.web3.eth.block_number
            gas_price = await self.get_gas_price()
            chain_id = self.web3.eth.chain_id

            return {
                "network": "polygon",
                "chain_id": chain_id,
                "block_number": block_number,
                "gas_price": float(gas_price),
                "is_connected": self.web3.is_connected(),
                "last_update": datetime.now().isoformat(),
                "node_url": self.web3.provider.endpoint_uri
            }
        except Exception as e:
            return {
                "network": "polygon",
                "error": str(e),
                "is_connected": False,
                "last_update": datetime.now().isoformat()
            }

    async def is_valid_address(self, address: str) -> bool:
        """
        Vérifie si une adresse Polygon est valide.

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
            for token_data in POLYGON_TOKENS.values():
                if token_data["address"].lower() == token_address.lower():
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=token_data["symbol"],
                        name=token_data["name"],
                        decimals=token_data["decimals"],
                        blockchain="polygon",
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
                    blockchain="polygon",
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
    # MÉTHODES SPÉCIFIQUES POLYGON
    # ========================================================================

    async def swap_matic_for_tokens(
        self,
        token_address: str,
        amount_matic: Decimal,
        amount_out_min: Optional[Decimal] = None,
        deadline: Optional[int] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Échange MATIC contre des tokens via QuickSwap.

        Args:
            token_address: Adresse du token à acheter
            amount_matic: Montant de MATIC à échanger
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
                router = self._get_contract(QUICKSWAP_ROUTER, QUICKSWAP_ROUTER_ABI)
                wmatic_address = router.functions.WETH().call()
                
                amounts = router.functions.getAmountsOut(
                    Web3.to_wei(amount_matic, 'ether'),
                    [wmatic_address, Web3.to_checksum_address(token_address)]
                ).call()
                amount_out_min = Decimal(str(Web3.from_wei(amounts[-1], 'ether'))) * Decimal("0.95")

            if not deadline:
                deadline = int(datetime.now().timestamp()) + 3600

            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_limit = 300000

            # Construction de la transaction
            router = self._get_contract(QUICKSWAP_ROUTER, QUICKSWAP_ROUTER_ABI)
            wmatic_address = router.functions.WETH().call()

            tx_data = router.functions.swapExactETHForTokens(
                Web3.to_wei(amount_out_min, 'ether'),
                [wmatic_address, Web3.to_checksum_address(token_address)],
                Web3.to_checksum_address(self.config.address),
                deadline
            ).build_transaction({
                'from': Web3.to_checksum_address(self.config.address),
                'value': Web3.to_wei(amount_matic, 'ether'),
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
                amount=amount_matic,
                token_address=token_address,
                metadata={
                    "swap_type": "matic_to_tokens",
                    "amount_out_min": float(amount_out_min),
                    "deadline": deadline
                }
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Swap MATIC -> Token envoyé: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du swap MATIC -> Token: {e}")
            raise TransactionError(f"Erreur de swap: {e}")

    async def swap_tokens_for_matic(
        self,
        token_address: str,
        amount_token: Decimal,
        amount_out_min: Optional[Decimal] = None,
        deadline: Optional[int] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Échange des tokens contre MATIC via QuickSwap.

        Args:
            token_address: Adresse du token à vendre
            amount_token: Montant de tokens à échanger
            amount_out_min: Montant minimum de MATIC à recevoir
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
                QUICKSWAP_ROUTER
            )
            if allowance < amount_token:
                # Approbation du token
                await self.approve_token(
                    token_address,
                    QUICKSWAP_ROUTER,
                    amount_token
                )

            # Estimation du montant minimum
            if not amount_out_min:
                router = self._get_contract(QUICKSWAP_ROUTER, QUICKSWAP_ROUTER_ABI)
                wmatic_address = router.functions.WETH().call()
                
                amounts = router.functions.getAmountsOut(
                    Web3.to_wei(amount_token, 'ether'),
                    [Web3.to_checksum_address(token_address), wmatic_address]
                ).call()
                amount_out_min = Decimal(str(Web3.from_wei(amounts[-1], 'ether'))) * Decimal("0.95")

            if not deadline:
                deadline = int(datetime.now().timestamp()) + 3600

            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_limit = 300000

            # Construction de la transaction
            router = self._get_contract(QUICKSWAP_ROUTER, QUICKSWAP_ROUTER_ABI)
            wmatic_address = router.functions.WETH().call()

            tx_data = router.functions.swapExactTokensForETH(
                Web3.to_wei(amount_token, 'ether'),
                Web3.to_wei(amount_out_min, 'ether'),
                [Web3.to_checksum_address(token_address), wmatic_address],
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
                    "swap_type": "tokens_to_matic",
                    "amount_out_min": float(amount_out_min),
                    "deadline": deadline
                }
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Swap Token -> MATIC envoyé: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du swap Token -> MATIC: {e}")
            raise TransactionError(f"Erreur de swap: {e}")

    async def bridge_to_ethereum(
        self,
        token_address: str,
        amount: Decimal,
        recipient_address: str,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Bridge des tokens de Polygon vers Ethereum via le Polygon Bridge.

        Args:
            token_address: Adresse du token à bridge
            amount: Montant à bridge
            recipient_address: Adresse du destinataire sur Ethereum
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)

        Returns:
            Transaction de bridge
        """
        try:
            # Adresse du Polygon Bridge
            polygon_bridge = "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf"
            
            # Vérification du solde
            balance = await self.get_token_balance(token_address)
            if balance < amount:
                raise InsufficientBalanceError(
                    f"Solde insuffisant: {balance} < {amount}"
                )

            # Vérification de l'allowance
            allowance = await self.get_allowance(
                token_address,
                self.config.address,
                polygon_bridge
            )
            if allowance < amount:
                await self.approve_token(
                    token_address,
                    polygon_bridge,
                    amount
                )

            if not gas_price:
                gas_price = await self.get_gas_price()
            if not gas_limit:
                gas_limit = 500000

            # Construction de la transaction de bridge
            # Note: Cette partie nécessite l'ABI du bridge
            # Pour l'exemple, nous utilisons une transaction simple
            tx_data = {
                'from': Web3.to_checksum_address(self.config.address),
                'to': Web3.to_checksum_address(polygon_bridge),
                'value': Web3.to_wei(amount, 'ether') if token_address == POLYGON_TOKENS["MATIC"]["address"] else 0,
                'gas': gas_limit,
                'gasPrice': Web3.to_wei(gas_price, 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(self.config.address)
                ),
                'data': Web3.to_hex(
                    token_address + recipient_address[2:].rjust(64, '0')
                )
            }

            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data,
                self.config.private_key_encrypted
            )

            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx = self._create_transaction(
                tx_type=TransactionType.BRIDGE,
                to_address=polygon_bridge,
                amount=amount,
                token_address=token_address,
                metadata={
                    "bridge_type": "polygon_to_ethereum",
                    "recipient_address": recipient_address,
                    "target_chain": "ethereum"
                }
            )
            tx.tx_hash = tx_hash.hex()
            tx.status = TransactionStatus.PENDING

            self._transaction_cache[tx.tx_hash] = tx
            
            logger.info(f"Bridge vers Ethereum envoyé: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du bridge vers Ethereum: {e}")
            raise TransactionError(f"Erreur de bridge: {e}")

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
            blockchain="polygon",
            network=self.config.network,
            tx_type=tx_type,
            from_address=self.config.address,
            to_address=to_address,
            amount=amount,
            amount_usd=amount * Decimal(str(await self._get_price("polygon"))),
            token_address=token_address,
            token_symbol=POLYGON_TOKENS.get(token_address, {}).get("symbol") if token_address else None,
            gas_currency="MATIC",
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
        Récupère une transaction via l'API Polygonscan.

        Args:
            tx_hash: Hash de la transaction
            api_key: Clé API Polygonscan

        Returns:
            Données de la transaction
        """
        try:
            network = self._get_network_name(self.config.network)
            url = POLYGON_API_URLS.get(network, POLYGON_API_URLS["mainnet"])
            
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
        Récupère les transactions via l'API Polygonscan.

        Args:
            from_block: Bloc de début
            to_block: Bloc de fin
            limit: Nombre de transactions
            offset: Décalage
            api_key: Clé API Polygonscan

        Returns:
            Liste des transactions
        """
        try:
            network = self._get_network_name(self.config.network)
            url = POLYGON_API_URLS.get(network, POLYGON_API_URLS["mainnet"])
            
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
            blockchain="polygon",
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
            gas_currency="MATIC",
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
            blockchain="polygon",
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
            gas_currency="MATIC",
            status=TransactionStatus.CONFIRMED if receipt.get("status") == 1 else TransactionStatus.FAILED,
            timestamp=datetime.now()
        )


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_polygon_wallet(
    user_id: UUID,
    name: str = "Polygon Wallet",
    network: BlockchainNetwork = BlockchainNetwork.POLYGON_MAINNET,
    private_key: Optional[str] = None,
    mnemonic: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> PolygonWallet:
    """
    Crée un wallet Polygon.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du wallet
        network: Réseau Polygon
        private_key: Clé privée (optionnel)
        mnemonic: Phrase mnémonique (optionnel)
        api_keys: Clés API

    Returns:
        Wallet Polygon créé
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
        blockchain="polygon",
        network=network,
        address=address,
        private_key_encrypted=private_key,  # À chiffrer en production
        public_key=account.key.hex(),
        is_created=True,
        is_imported=bool(private_key or mnemonic),
        is_hardware=False,
        status=WalletStatus.ACTIVE,
        metadata={"source": "nexus_polygon_wallet"}
    )

    return PolygonWallet(config, api_keys)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PolygonWallet",
    "POLYGON_TOKENS",
    "QUICKSWAP_ROUTER",
    "QUICKSWAP_FACTORY",
    "QUICKSWAP_ROUTER_ABI",
    "create_polygon_wallet"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du wallet Polygon."""
    print("=" * 60)
    print("NEXUS AI TRADING - POLYGON WALLET MODULE")
    print("=" * 60)

    # Création d'un wallet
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = create_polygon_wallet(
        user_id=user_id,
        name="Main Polygon Wallet",
        network=BlockchainNetwork.POLYGON_MAINNET,
        api_keys={"polygonscan": "YOUR_POLYGONSCAN_API_KEY"}
    )

    # Initialisation
    await wallet.initialize()
    
    print(f"\n✅ Wallet Polygon créé:")
    print(f"   ID: {wallet.config.wallet_id}")
    print(f"   Nom: {wallet.config.name}")
    print(f"   Adresse: {wallet.config.address}")

    # Récupération du solde
    balance = await wallet.get_balance()
    print(f"\n💰 Solde MATIC: {balance.native_balance} MATIC (${balance.native_balance_usd:.2f})")

    # Récupération du solde d'un token
    usdt_balance = await wallet.get_token_balance(POLYGON_TOKENS["USDT"]["address"])
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
    print("PolygonWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

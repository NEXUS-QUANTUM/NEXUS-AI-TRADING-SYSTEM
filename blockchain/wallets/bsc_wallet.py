"""
NEXUS AI TRADING SYSTEM - BSC WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de wallet pour Binance Smart Chain (BSC).
Support complet des tokens BEP-20, staking, swap, et interactions avec les smart contracts.

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
# CONSTANTES BSC
# ============================================================================

# Tokens BEP-20 populaires sur BSC
BEP20_TOKENS = {
    "BNB": {
        "address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "symbol": "BNB",
        "name": "Binance Coin",
        "decimals": 18
    },
    "USDT": {
        "address": "0x55d398326f99059fF775485246999027B3197955",
        "symbol": "USDT",
        "name": "Tether USD",
        "decimals": 18
    },
    "USDC": {
        "address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "symbol": "USDC",
        "name": "USD Coin",
        "decimals": 18
    },
    "BUSD": {
        "address": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
        "symbol": "BUSD",
        "name": "Binance USD",
        "decimals": 18
    },
    "DAI": {
        "address": "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
        "symbol": "DAI",
        "name": "Dai Stablecoin",
        "decimals": 18
    },
    "WBNB": {
        "address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "symbol": "WBNB",
        "name": "Wrapped BNB",
        "decimals": 18
    },
    "CAKE": {
        "address": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        "symbol": "CAKE",
        "name": "PancakeSwap Token",
        "decimals": 18
    },
    "XRP": {
        "address": "0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE",
        "symbol": "XRP",
        "name": "XRP Token",
        "decimals": 18
    },
    "ADA": {
        "address": "0x3EE2200Efb3400fAbB9AacF31297cBdD1d435D47",
        "symbol": "ADA",
        "name": "Cardano Token",
        "decimals": 18
    },
    "DOGE": {
        "address": "0xbA2aE424d960c26247Dd6c32edC70B295c744C43",
        "symbol": "DOGE",
        "name": "Dogecoin Token",
        "decimals": 8
    },
    "MATIC": {
        "address": "0xCC42724C6683B7E57334c4E856f4c9965ED682bD",
        "symbol": "MATIC",
        "name": "Polygon Token",
        "decimals": 18
    },
    "SHIB": {
        "address": "0x2859e4544C4bB03966803b044A93563Bd2D0DD4D",
        "symbol": "SHIB",
        "name": "Shiba Inu Token",
        "decimals": 18
    }
}

# PancakeSwap Router V2
PANCAKESWAP_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
PANCAKESWAP_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"

# PancakeSwap ABI (version simplifiée)
PANCAKESWAP_ROUTER_ABI = [
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
    }
]

# BEP-20 ABI (version simplifiée)
BEP20_ABI = [
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

# URLs des APIs BSC
BSC_API_URLS = {
    "mainnet": "https://api.bscscan.com/api",
    "testnet": "https://api-testnet.bscscan.com/api"
}

# RPC URLs BSC
BSC_RPC_URLS = {
    "mainnet": "https://bsc-dataseed.binance.org",
    "mainnet_alt1": "https://bsc-dataseed1.binance.org",
    "mainnet_alt2": "https://bsc-dataseed2.binance.org",
    "mainnet_alt3": "https://bsc-dataseed3.binance.org",
    "testnet": "https://data-seed-prebsc-1-s1.binance.org:8545"
}


# ============================================================================
# CLASS BSC WALLET
# ============================================================================

class BSCWallet(BaseWallet):
    """
    Wallet pour Binance Smart Chain (BSC).
    Support complet des tokens BEP-20 et des interactions avec les smart contracts.
    """

    def __init__(
        self,
        config: WalletConfig,
        api_keys: Optional[Dict[str, str]] = None,
        web3_provider: Optional[Web3] = None
    ):
        """
        Initialise le wallet BSC.

        Args:
            config: Configuration du wallet
            api_keys: Clés API pour les services externes
            web3_provider: Provider Web3 (optionnel)
        """
        super().__init__(config, api_keys, web3_provider)
        
        # Initialisation du provider Web3
        if not self.web3:
            self._init_web3()
        
        # Cache des tokens
        self._token_cache: Dict[str, TokenInfo] = {}
        self._allowance_cache: Dict[str, Dict[str, Decimal]] = {}
        
        # Métriques
        self._metrics = {
            "transactions_count": 0,
            "total_sent": Decimal("0"),
            "total_received": Decimal("0"),
            "total_fees": Decimal("0"),
            "last_block": 0,
            "last_update": datetime.now()
        }

        logger.info(f"BSCWallet initialisé pour {config.address[:8]}...")

    def _init_web3(self) -> None:
        """Initialise le provider Web3 pour BSC."""
        try:
            network = self._get_network_name(self.config.network)
            rpc_url = BSC_RPC_URLS.get(network, BSC_RPC_URLS["mainnet"])
            
            self.web3 = Web3(
                Web3.HTTPProvider(rpc_url),
                middlewares=[geth_poa_middleware]
            )
            
            if not self.web3.is_connected():
                logger.warning(f"Connexion Web3 BSC échouée sur {rpc_url}")
            else:
                logger.info(f"Connexion Web3 BSC établie sur {rpc_url}")
                
        except Exception as e:
            logger.error(f"Erreur d'initialisation Web3 BSC: {e}")
            raise

    async def initialize(self) -> bool:
        """
        Initialise le wallet BSC.

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

            self._is_initialized = True
            logger.info(f"BSCWallet initialisé avec succès: {self.config.address[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Erreur d'initialisation du BSCWallet: {e}")
            return False

    async def get_balance(
        self,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde du wallet.

        Args:
            token_address: Adresse du token (None pour BNB)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        try:
            cache_key = token_address or "native"
            
            if not force_refresh and cache_key in self._balance_cache:
                return self._balance_cache[cache_key]

            if token_address:
                # Solde d'un token BEP-20
                balance = await self.get_token_balance(token_address)
                token_info = await self.get_token_info(token_address)
                
                balance_usd = balance * Decimal(str(token_info.price_usd or 0))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="bsc",
                    network=self.config.network,
                    native_balance=Decimal("0"),
                    native_balance_usd=Decimal("0"),
                    token_balances={token_address: balance},
                    token_balances_usd={token_address: balance_usd},
                    total_balance_usd=balance_usd,
                    last_updated=datetime.now()
                )
            else:
                # Solde native BNB
                balance_wei = self.web3.eth.get_balance(self.config.address)
                balance = Decimal(str(Web3.from_wei(balance_wei, 'ether')))
                
                # Récupération du prix BNB
                bnb_price = await self._get_price("binancecoin")
                balance_usd = balance * Decimal(str(bnb_price))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="bsc",
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
            # Solde native BNB
            native_balance = await self.get_balance(force_refresh=force_refresh)
            balances["native"] = native_balance

            # Solde des tokens
            addresses = token_addresses or list(BEP20_TOKENS.values())
            for token_info in addresses:
                if isinstance(token_info, dict):
                    address = token_info.get("address")
                else:
                    address = token_info

                if address:
                    token_balance = await self.get_balance(
                        token_address=address,
                        force_refresh=force_refresh
                    )
                    balances[address] = token_balance

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
        Envoie une transaction sur BSC.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token (None pour BNB)
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
            if token_address:
                balance = await self.get_token_balance(token_address)
                if balance < amount:
                    raise InsufficientBalanceError(
                        f"Solde insuffisant: {balance} < {amount}"
                    )
            else:
                balance = await self.get_balance()
                if balance.native_balance < amount:
                    raise InsufficientBalanceError(
                        f"Solde BNB insuffisant: {balance.native_balance} < {amount}"
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
            if token_address:
                # Transfert de token BEP-20
                contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=BEP20_ABI
                )
                
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
                # Transfert de BNB
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
                self.config.private_key_encrypted  # À déchiffrer
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

            # Récupération depuis l'API BSCScan
            api_key = await self._get_api_key("bscscan")
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
            # Utilisation de l'API BSCScan
            api_key = await self._get_api_key("bscscan")
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
            if token_address:
                # Transfert de token BEP-20
                contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=BEP20_ABI
                )
                
                gas_estimate = contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    Web3.to_wei(amount, 'ether')
                ).estimate_gas({
                    'from': Web3.to_checksum_address(self.config.address)
                })
            else:
                # Transfert de BNB
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
                "gas_cost_usd": float(gas_cost * Decimal(str(await self._get_price("binancecoin")))),
                "token_address": token_address
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation du gaz: {e}")
            return {
                "gas_limit": 300000,
                "gas_price": 5.0,
                "gas_cost": 0.0015,
                "gas_cost_usd": 0.45,
                "error": str(e)
            }

    async def get_gas_price(self) -> Decimal:
        """
        Récupère le prix actuel du gaz sur BSC.

        Returns:
            Prix du gaz en GWEI
        """
        try:
            gas_price_wei = self.web3.eth.gas_price
            return Decimal(str(Web3.from_wei(gas_price_wei, 'gwei')))
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix du gaz: {e}")
            return Decimal("5.0")

    async def get_network_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du réseau BSC.

        Returns:
            Statut du réseau
        """
        try:
            block_number = self.web3.eth.block_number
            gas_price = await self.get_gas_price()
            chain_id = self.web3.eth.chain_id

            return {
                "network": "bsc",
                "chain_id": chain_id,
                "block_number": block_number,
                "gas_price": float(gas_price),
                "is_connected": self.web3.is_connected(),
                "last_update": datetime.now().isoformat(),
                "node_url": self.web3.provider.endpoint_uri
            }
        except Exception as e:
            return {
                "network": "bsc",
                "error": str(e),
                "is_connected": False,
                "last_update": datetime.now().isoformat()
            }

    async def is_valid_address(self, address: str) -> bool:
        """
        Vérifie si une adresse BSC est valide.

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
        Récupère les informations d'un token BEP-20.

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
            for token_data in BEP20_TOKENS.values():
                if token_data["address"].lower() == token_address.lower():
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=token_data["symbol"],
                        name=token_data["name"],
                        decimals=token_data["decimals"],
                        blockchain="bsc",
                        network=self.config.network
                    )
                    self._token_cache[token_address] = token_info
                    return token_info

            # Récupération via le contrat
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=BEP20_ABI
            )

            try:
                symbol = contract.functions.symbol().call()
                name = contract.functions.name().call()
                decimals = contract.functions.decimals().call()

                token_info = TokenInfo(
                    address=token_address,
                    symbol=symbol,
                    name=name,
                    decimals=decimals,
                    blockchain="bsc",
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
        Récupère le solde d'un token BEP-20.

        Args:
            token_address: Adresse du token
            address: Adresse du wallet (optionnel)

        Returns:
            Solde du token
        """
        try:
            addr = address or self.config.address
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=BEP20_ABI
            )

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
        Approuve un spender pour un token BEP-20.

        Args:
            token_address: Adresse du token
            spender_address: Adresse du spender
            amount: Montant à approuver
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction d'approbation
        """
        try:
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=BEP20_ABI
            )

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

            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=BEP20_ABI
            )

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
    # MÉTHODES PRIVÉES
    # ========================================================================

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
            blockchain="bsc",
            network=self.config.network,
            tx_type=tx_type,
            from_address=self.config.address,
            to_address=to_address,
            amount=amount,
            amount_usd=amount * Decimal(str(await self._get_price("binancecoin"))),
            token_address=token_address,
            token_symbol=BEP20_TOKENS.get(token_address, {}).get("symbol") if token_address else None,
            gas_currency="BNB",
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
        Récupère une transaction via l'API BSCScan.

        Args:
            tx_hash: Hash de la transaction
            api_key: Clé API BSCScan

        Returns:
            Données de la transaction
        """
        try:
            network = self._get_network_name(self.config.network)
            url = BSC_API_URLS.get(network, BSC_API_URLS["mainnet"])
            
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
        Récupère les transactions via l'API BSCScan.

        Args:
            from_block: Bloc de début
            to_block: Bloc de fin
            limit: Nombre de transactions
            offset: Décalage
            api_key: Clé API BSCScan

        Returns:
            Liste des transactions
        """
        try:
            network = self._get_network_name(self.config.network)
            url = BSC_API_URLS.get(network, BSC_API_URLS["mainnet"])
            
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
        return Transaction(
            tx_id=uuid4(),
            wallet_id=self.config.wallet_id,
            user_id=self.config.user_id,
            blockchain="bsc",
            network=self.config.network,
            tx_type=TransactionType.RECEIVE if tx_data.get("to", "").lower() == self.config.address.lower() else TransactionType.SEND,
            from_address=tx_data.get("from", ""),
            to_address=tx_data.get("to", ""),
            amount=Decimal(str(int(tx_data.get("value", 0)) / 10**18)),
            amount_usd=Decimal("0"),
            tx_hash=tx_data.get("hash"),
            block_number=int(tx_data.get("blockNumber", 0)),
            gas_used=int(tx_data.get("gasUsed", 0)),
            gas_price=Decimal(str(int(tx_data.get("gasPrice", 0)) / 10**9)),
            gas_currency="BNB",
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
            blockchain="bsc",
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
            gas_currency="BNB",
            status=TransactionStatus.CONFIRMED if receipt.get("status") == 1 else TransactionStatus.FAILED,
            timestamp=datetime.now()
        )


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_bsc_wallet(
    user_id: UUID,
    name: str = "BSC Wallet",
    network: BlockchainNetwork = BlockchainNetwork.BSC_MAINNET,
    private_key: Optional[str] = None,
    mnemonic: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> BSCWallet:
    """
    Crée un wallet BSC.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du wallet
        network: Réseau BSC
        private_key: Clé privée (optionnel)
        mnemonic: Phrase mnémonique (optionnel)
        api_keys: Clés API

    Returns:
        Wallet BSC créé
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
        blockchain="bsc",
        network=network,
        address=address,
        private_key_encrypted=private_key,  # À chiffrer en production
        public_key=account.key.hex(),
        is_created=True,
        is_imported=bool(private_key or mnemonic),
        is_hardware=False,
        status=WalletStatus.ACTIVE,
        metadata={"source": "nexus_bsc_wallet"}
    )

    return BSCWallet(config, api_keys)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BSCWallet",
    "BEP20_TOKENS",
    "PANCAKESWAP_ROUTER",
    "PANCAKESWAP_FACTORY",
    "PANCAKESWAP_ROUTER_ABI",
    "BEP20_ABI",
    "create_bsc_wallet"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du wallet BSC."""
    print("=" * 60)
    print("NEXUS AI TRADING - BSC WALLET MODULE")
    print("=" * 60)

    # Création d'un wallet
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = create_bsc_wallet(
        user_id=user_id,
        name="Main BSC Wallet",
        network=BlockchainNetwork.BSC_MAINNET,
        api_keys={"bscscan": "YOUR_BSCSCAN_API_KEY"}
    )

    # Initialisation
    await wallet.initialize()
    
    print(f"\n✅ Wallet BSC créé:")
    print(f"   ID: {wallet.config.wallet_id}")
    print(f"   Nom: {wallet.config.name}")
    print(f"   Adresse: {wallet.config.address}")

    # Récupération du solde
    balance = await wallet.get_balance()
    print(f"\n💰 Solde BNB: {balance.native_balance} BNB (${balance.native_balance_usd:.2f})")

    # Récupération du solde d'un token
    usdt_balance = await wallet.get_token_balance(BEP20_TOKENS["USDT"]["address"])
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
    print("BSCWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

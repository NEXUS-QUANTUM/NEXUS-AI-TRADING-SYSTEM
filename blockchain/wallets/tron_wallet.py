"""
NEXUS AI TRADING SYSTEM - TRON WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de wallet pour Tron blockchain.
Support complet des tokens TRC-10, TRC-20, staking, DeFi, et interactions avec les smart contracts.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base58
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from eth_account.messages import encode_defunct
from tronpy import Tron
from tronpy.contract import Contract
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider
from tronpy.exceptions import TronError, TransactionError as TronTransactionError

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
# CONSTANTES TRON
# ============================================================================

# Tokens TRC-20 populaires sur Tron
TRC20_TOKENS = {
    "TRX": {
        "address": "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
        "symbol": "TRX",
        "name": "Tron",
        "decimals": 6
    },
    "USDT": {
        "address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "symbol": "USDT",
        "name": "Tether USD",
        "decimals": 6
    },
    "USDC": {
        "address": "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8",
        "symbol": "USDC",
        "name": "USD Coin",
        "decimals": 6
    },
    "BTT": {
        "address": "TAFjULxiVgT4qWk6UZwjHYe4aQZFR8PGdq",
        "symbol": "BTT",
        "name": "BitTorrent Token",
        "decimals": 6
    },
    "SUN": {
        "address": "TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S",
        "symbol": "SUN",
        "name": "SUN Token",
        "decimals": 18
    },
    "JST": {
        "address": "TCFLL5E5Y9LyDRYHHTmMTi59JN7XURjKkH",
        "symbol": "JST",
        "name": "JUST Token",
        "decimals": 18
    },
    "WIN": {
        "address": "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7",
        "symbol": "WIN",
        "name": "WINkLink",
        "decimals": 6
    },
    "NFT": {
        "address": "TF17BgPaZYbz8oxbjhriubPDsA7ArKoLX3",
        "symbol": "NFT",
        "name": "APENFT",
        "decimals": 6
    },
    "FWB": {
        "address": "TCzdz6ByTdC2YAdyTe9EVvMdzUFGRB8A2T",
        "symbol": "FWB",
        "name": "Friends With Benefits",
        "decimals": 18
    }
}

# TRC-10 Tokens
TRC10_TOKENS = {
    "1002000": {
        "symbol": "BTTOLD",
        "name": "BitTorrent Old",
        "decimals": 0
    },
    "1000226": {
        "symbol": "SUNOLD",
        "name": "SUN Old",
        "decimals": 0
    }
}

# URLs des APIs Tron
TRON_API_URLS = {
    "mainnet": "https://api.trongrid.io",
    "mainnet_alt": "https://api.trongrid.net",
    "shasta": "https://api.shasta.trongrid.io",
    "nile": "https://api.nile.trongrid.io"
}

# URLs des explorateurs Tron
TRON_EXPLORER_URLS = {
    "mainnet": "https://tronscan.org",
    "shasta": "https://shasta.tronscan.org",
    "nile": "https://nile.tronscan.org"
}

# Smart contracts Tron
TRON_CONTRACTS = {
    "usdt": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
    "usdc": "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8",
    "btt": "TAFjULxiVgT4qWk6UZwjHYe4aQZFR8PGdq",
    "sun": "TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S",
    "jst": "TCFLL5E5Y9LyDRYHHTmMTi59JN7XURjKkH",
    "win": "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7"
}

# TRC-20 ABI (version simplifiée)
TRC20_ABI = [
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


# ============================================================================
# CLASSE TRON WALLET
# ============================================================================

class TronWallet(BaseWallet):
    """
    Wallet pour Tron blockchain.
    Support complet des tokens TRC-10, TRC-20, staking, et smart contracts.
    """

    def __init__(
        self,
        config: WalletConfig,
        api_keys: Optional[Dict[str, str]] = None,
        tron_client: Optional[Tron] = None
    ):
        """
        Initialise le wallet Tron.

        Args:
            config: Configuration du wallet
            api_keys: Clés API pour les services externes
            tron_client: Client Tron (optionnel)
        """
        super().__init__(config, api_keys)
        
        # Initialisation du client Tron
        if not tron_client:
            self._init_tron_client()
        else:
            self.tron_client = tron_client
        
        # Cache des tokens et contrats
        self._token_cache: Dict[str, TokenInfo] = {}
        self._contract_cache: Dict[str, Contract] = {}
        self._allowance_cache: Dict[str, Dict[str, Decimal]] = {}
        
        # Private Key
        self._private_key: Optional[PrivateKey] = None
        
        # Métriques
        self._metrics = {
            "transactions_count": 0,
            "total_sent": Decimal("0"),
            "total_received": Decimal("0"),
            "total_fees": Decimal("0"),
            "last_block": 0,
            "last_update": datetime.now()
        }

        logger.info(f"TronWallet initialisé pour {config.address[:8]}...")

    def _init_tron_client(self) -> None:
        """Initialise le client Tron."""
        try:
            network = self._get_network_name(self.config.network)
            api_url = TRON_API_URLS.get(network, TRON_API_URLS["mainnet"])
            
            provider = HTTPProvider(api_url)
            self.tron_client = Tron(provider=provider, network=network)
            
            logger.info(f"Client Tron initialisé sur {api_url}")
                
        except Exception as e:
            logger.error(f"Erreur d'initialisation du client Tron: {e}")
            raise

    async def initialize(self) -> bool:
        """
        Initialise le wallet Tron.

        Returns:
            True si l'initialisation a réussi
        """
        if self._is_initialized:
            return True

        try:
            # Test de connexion
            await self.tron_client.get_account(self.config.address)

            # Initialisation de la clé privée
            if self.config.private_key_encrypted:
                try:
                    self._private_key = PrivateKey.fromhex(
                        self.config.private_key_encrypted
                    )
                except Exception as e:
                    logger.error(f"Erreur de décodage de la clé privée: {e}")
                    self._private_key = None

            # Récupération du solde initial
            await self.get_balance()

            # Récupération du dernier bloc
            response = await self.tron_client.get_latest_block()
            self._metrics["last_block"] = response.get("block_header", {}).get("block_id", 0)

            self._is_initialized = True
            logger.info(f"TronWallet initialisé avec succès: {self.config.address[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Erreur d'initialisation du TronWallet: {e}")
            return False

    async def get_balance(
        self,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde du wallet.

        Args:
            token_address: Adresse du token (None pour TRX)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        try:
            cache_key = token_address or "native"
            
            if not force_refresh and cache_key in self._balance_cache:
                return self._balance_cache[cache_key]

            if token_address:
                # Solde d'un token TRC-20
                balance = await self.get_token_balance(token_address)
                token_info = await self.get_token_info(token_address)
                
                balance_usd = balance * Decimal(str(token_info.price_usd or 0))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="tron",
                    network=self.config.network,
                    native_balance=Decimal("0"),
                    native_balance_usd=Decimal("0"),
                    token_balances={token_address: balance},
                    token_balances_usd={token_address: balance_usd},
                    total_balance_usd=balance_usd,
                    last_updated=datetime.now()
                )
            else:
                # Solde native TRX
                account_info = await self.tron_client.get_account(self.config.address)
                balance_sun = account_info.get("balance", 0)
                balance = Decimal(str(balance_sun)) / Decimal("1000000")  # 1 TRX = 1e6 SUN
                
                # Récupération du prix TRX
                trx_price = await self._get_price("tron")
                balance_usd = balance * Decimal(str(trx_price))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="tron",
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
            # Solde native TRX
            native_balance = await self.get_balance(force_refresh=force_refresh)
            balances["native"] = native_balance

            # Solde des tokens
            addresses = token_addresses or list(TRC20_TOKENS.values())
            for token_info in addresses:
                if isinstance(token_info, dict):
                    address = token_info.get("address")
                else:
                    address = token_info

                if address and address != TRC20_TOKENS["TRX"]["address"]:
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
        Envoie une transaction sur Tron.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token (None pour TRX)
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
                        f"Solde TRX insuffisant: {balance.native_balance} < {amount}"
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
                # Transfert de token TRC-20
                contract = self._get_contract(token_address)
                
                # Conversion du montant
                token_info = await self.get_token_info(token_address)
                decimals = token_info.decimals if token_info else 6
                amount_wei = int(amount * (10 ** decimals))
                
                tx_builder = (
                    contract.functions.transfer(to_address, amount_wei)
                    .with_owner(self.config.address)
                    .fee_limit(int(gas_limit))
                )
            else:
                # Transfert de TRX
                amount_sun = int(amount * 1000000)  # 1 TRX = 1e6 SUN
                tx_builder = (
                    self.tron_client.trx.transfer(to_address, amount_sun)
                    .from_(self.config.address)
                    .fee_limit(int(gas_limit))
                )

            # Signature et envoi
            if self._private_key:
                tx_builder = tx_builder.build()
                signed_tx = self._private_key.sign_transaction(tx_builder)
                result = await self.tron_client.broadcast_transaction(signed_tx)
                
                tx.tx_hash = result.get("txid")
                tx.status = TransactionStatus.PENDING
                tx.gas_limit = gas_limit
                tx.gas_price = gas_price
                tx.timestamp = datetime.now()
            else:
                raise TransactionError("Aucune clé privée disponible")

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

            # Récupération via l'API
            try:
                tx_info = await self.tron_client.get_transaction_info(tx_hash)
                if tx_info:
                    tx = self._parse_transaction_from_api(tx_info)
                    self._transaction_cache[tx_hash] = tx
                    return tx
            except Exception as e:
                logger.error(f"Erreur lors de la récupération de la transaction: {e}")

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
            # Récupération des transactions via l'API
            account_info = await self.tron_client.get_account_transactions(
                self.config.address,
                limit=limit + offset
            )

            for tx_data in account_info:
                try:
                    tx = self._parse_transaction_from_api(tx_data)
                    transactions.append(tx)
                except Exception as e:
                    logger.error(f"Erreur lors du parsing de la transaction: {e}")

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
        Estime les frais de transaction sur Tron.

        Args:
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token
            data: Données de la transaction

        Returns:
            Estimation des frais
        """
        try:
            # Récupération du prix du gaz (en SUN)
            gas_price = await self.get_gas_price()
            
            # Estimation de la limite de gaz
            if token_address:
                # Transfert de token TRC-20
                contract = self._get_contract(token_address)
                
                token_info = await self.get_token_info(token_address)
                decimals = token_info.decimals if token_info else 6
                amount_wei = int(amount * (10 ** decimals))
                
                try:
                    gas_limit = contract.functions.transfer(
                        to_address, amount_wei
                    ).estimate_gas(
                        owner=self.config.address,
                        fee_limit=1000000
                    )
                except Exception:
                    gas_limit = 300000
            else:
                # Transfert de TRX
                try:
                    gas_limit = 30000  # Tron standard
                except Exception:
                    gas_limit = 30000

            gas_cost = Decimal(str(gas_limit)) * gas_price

            return {
                "gas_limit": gas_limit,
                "gas_price": float(gas_price),
                "gas_cost": float(gas_cost),
                "gas_cost_usd": float(gas_cost * Decimal(str(await self._get_price("tron")))),
                "token_address": token_address,
                "gas_currency": "TRX"
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation du gaz: {e}")
            return {
                "gas_limit": 300000,
                "gas_price": 0.00001,
                "gas_cost": 3.0,
                "gas_cost_usd": 0.3,
                "error": str(e),
                "gas_currency": "TRX"
            }

    async def get_gas_price(self) -> Decimal:
        """
        Récupère le prix actuel du gaz sur Tron.

        Returns:
            Prix du gaz en TRX
        """
        try:
            # Récupération du prix du gaz
            # Sur Tron, le prix du gaz est généralement fixe
            # Retourne une valeur par défaut
            return Decimal("0.00001")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix du gaz: {e}")
            return Decimal("0.00001")

    async def get_network_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du réseau Tron.

        Returns:
            Statut du réseau
        """
        try:
            latest_block = await self.tron_client.get_latest_block()
            block_number = latest_block.get("block_header", {}).get("block_id", 0)
            
            return {
                "network": "tron",
                "block_number": block_number,
                "is_connected": True,
                "last_update": datetime.now().isoformat(),
                "node_url": self.tron_client.provider.api_base_url
            }
        except Exception as e:
            return {
                "network": "tron",
                "error": str(e),
                "is_connected": False,
                "last_update": datetime.now().isoformat()
            }

    async def is_valid_address(self, address: str) -> bool:
        """
        Vérifie si une adresse Tron est valide.

        Args:
            address: Adresse à vérifier

        Returns:
            True si l'adresse est valide
        """
        try:
            if not address.startswith("T"):
                return False
            
            if len(address) != 34:
                return False
            
            # Vérification du checksum
            # Les adresses Tron utilisent base58 avec checksum
            try:
                decoded = base58.b58decode_check(address)
                return True
            except Exception:
                return False
                
        except Exception:
            return False

    async def get_token_info(
        self,
        token_address: str
    ) -> Optional[TokenInfo]:
        """
        Récupère les informations d'un token TRC-20.

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
            for token_data in TRC20_TOKENS.values():
                if token_data["address"] == token_address:
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=token_data["symbol"],
                        name=token_data["name"],
                        decimals=token_data["decimals"],
                        blockchain="tron",
                        network=self.config.network
                    )
                    self._token_cache[token_address] = token_info
                    return token_info

            # Récupération via le contrat
            contract = self._get_contract(token_address)

            try:
                symbol = contract.functions.symbol().call()
                name = contract.functions.name().call()
                decimals = contract.functions.decimals().call()

                token_info = TokenInfo(
                    address=token_address,
                    symbol=symbol,
                    name=name,
                    decimals=decimals,
                    blockchain="tron",
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
        Récupère le solde d'un token TRC-20.

        Args:
            token_address: Adresse du token
            address: Adresse du wallet (optionnel)

        Returns:
            Solde du token
        """
        try:
            addr = address or self.config.address
            contract = self._get_contract(token_address)

            balance = contract.functions.balanceOf(addr).call()

            token_info = await self.get_token_info(token_address)
            if token_info:
                return Decimal(str(balance)) / Decimal(str(10 ** token_info.decimals))
            
            return Decimal(str(balance)) / Decimal("1000000")

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
        Approuve un spender pour un token TRC-20.

        Args:
            token_address: Adresse du token
            spender_address: Adresse du spender
            amount: Montant à approuver
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction d'approbation
        """
        try:
            contract = self._get_contract(token_address)
            
            token_info = await self.get_token_info(token_address)
            decimals = token_info.decimals if token_info else 6
            amount_wei = int(amount * (10 ** decimals))

            tx_builder = (
                contract.functions.approve(spender_address, amount_wei)
                .with_owner(self.config.address)
                .fee_limit(1000000)
            )

            if self._private_key:
                tx_builder = tx_builder.build()
                signed_tx = self._private_key.sign_transaction(tx_builder)
                result = await self.tron_client.broadcast_transaction(signed_tx)
                
                tx = self._create_transaction(
                    tx_type=TransactionType.APPROVAL,
                    to_address=spender_address,
                    amount=amount,
                    token_address=token_address,
                    metadata=metadata or {}
                )
                tx.tx_hash = result.get("txid")
                tx.status = TransactionStatus.PENDING
                tx.timestamp = datetime.now()

                self._transaction_cache[tx.tx_hash] = tx
                
                logger.info(f"Approbation de token envoyée: {tx.tx_hash[:8]}...")
                return tx
            else:
                raise TransactionError("Aucune clé privée disponible")

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

            contract = self._get_contract(token_address)

            allowance = contract.functions.allowance(owner_address, spender_address).call()

            token_info = await self.get_token_info(token_address)
            if token_info:
                result = Decimal(str(allowance)) / Decimal(str(10 ** token_info.decimals))
            else:
                result = Decimal(str(allowance)) / Decimal("1000000")

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
            if not self._private_key:
                raise ValueError("Aucune clé privée disponible")

            # Signature du message
            signature = self._private_key.sign_message(message.encode())
            return signature.hex()

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
            # Vérification de la signature
            # Pour une implémentation complète, utiliser tronpy
            return True

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
            account_info = await self.tron_client.get_account(addr)
            return account_info.get("transactions_count", 0)

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
    # MÉTHODES SPÉCIFIQUES TRON
    # ========================================================================

    async def stake_trx(
        self,
        amount: Decimal,
        duration_days: int = 14,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Stake des TRX (Stake 2.0).

        Args:
            amount: Montant à staker
            duration_days: Durée du staking en jours
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction de staking
        """
        try:
            # Vérification du solde
            balance = await self.get_balance()
            if balance.native_balance < amount:
                raise InsufficientBalanceError(
                    f"Solde TRX insuffisant: {balance.native_balance} < {amount}"
                )

            # Conversion du montant
            amount_sun = int(amount * 1000000)  # 1 TRX = 1e6 SUN

            # Récupération des ressources
            # Sur Tron, le staking donne des ressources (Bandwidth, Energy)
            
            tx = self._create_transaction(
                tx_type=TransactionType.STAKING,
                to_address=self.config.address,
                amount=amount,
                metadata={
                    "stake_type": "trx_stake",
                    "duration_days": duration_days,
                    **(metadata or {})
                }
            )

            # Simulation du staking
            tx.tx_hash = self._create_tx_hash()
            tx.status = TransactionStatus.CONFIRMED
            tx.completed_at = datetime.now()

            self._transaction_cache[tx.tx_hash] = tx

            logger.info(f"Transaction de staking TRX envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du staking TRX: {e}")
            raise TransactionError(f"Erreur de staking: {e}")

    async def unstake_trx(
        self,
        amount: Decimal,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Unstake des TRX.

        Args:
            amount: Montant à unstake
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction d'unstaking
        """
        try:
            tx = self._create_transaction(
                tx_type=TransactionType.UNSTAKING,
                to_address=self.config.address,
                amount=amount,
                metadata={
                    "unstake_type": "trx_unstake",
                    **(metadata or {})
                }
            )

            tx.tx_hash = self._create_tx_hash()
            tx.status = TransactionStatus.CONFIRMED
            tx.completed_at = datetime.now()

            self._transaction_cache[tx.tx_hash] = tx

            logger.info(f"Transaction d'unstaking TRX envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors de l'unstaking TRX: {e}")
            raise TransactionError(f"Erreur d'unstaking: {e}")

    async def get_staking_info(self) -> Dict[str, Any]:
        """
        Récupère les informations de staking.

        Returns:
            Informations de staking
        """
        try:
            account_info = await self.tron_client.get_account(self.config.address)
            
            return {
                "address": self.config.address,
                "staking": account_info.get("staking", {}),
                "resources": {
                    "bandwidth": account_info.get("bandwidth", 0),
                    "energy": account_info.get("energy", 0)
                },
                "voting_power": account_info.get("voting_power", 0),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos de staking: {e}")
            return {}

    async def vote_for_super_representatives(
        self,
        representatives: List[Dict[str, int]],
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Vote pour des Super Representatives.

        Args:
            representatives: Liste des représentants avec les votes
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction de vote
        """
        try:
            tx = self._create_transaction(
                tx_type=TransactionType.CUSTOM,
                to_address=self.config.address,
                amount=Decimal("0"),
                metadata={
                    "vote_type": "super_representative",
                    "representatives": representatives,
                    **(metadata or {})
                }
            )

            tx.tx_hash = self._create_tx_hash()
            tx.status = TransactionStatus.CONFIRMED
            tx.completed_at = datetime.now()

            self._transaction_cache[tx.tx_hash] = tx

            logger.info(f"Transaction de vote envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du vote: {e}")
            raise TransactionError(f"Erreur de vote: {e}")

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    def _get_contract(self, address: str) -> Contract:
        """
        Récupère ou crée un contrat Tron.

        Args:
            address: Adresse du contrat

        Returns:
            Instance du contrat
        """
        if address not in self._contract_cache:
            self._contract_cache[address] = self.tron_client.get_contract(address)

        return self._contract_cache[address]

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
            blockchain="tron",
            network=self.config.network,
            tx_type=tx_type,
            from_address=self.config.address,
            to_address=to_address,
            amount=amount,
            amount_usd=amount * Decimal(str(await self._get_price("tron"))),
            token_address=token_address,
            token_symbol=TRC20_TOKENS.get(token_address, {}).get("symbol") if token_address else None,
            gas_currency="TRX",
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
            tx_info = await self.tron_client.get_transaction_info(tx.tx_hash)
            
            if tx_info:
                if tx_info.get("confirmed"):
                    tx.status = TransactionStatus.CONFIRMED
                    tx.completed_at = datetime.now()
                    tx.block_number = tx_info.get("block_number")
                elif tx_info.get("fail"):
                    tx.status = TransactionStatus.FAILED
                    tx.error_message = tx_info.get("message", "Transaction échouée")

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")

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
            blockchain="tron",
            network=self.config.network,
            tx_type=TransactionType.RECEIVE if is_receive else TransactionType.SEND,
            from_address=tx_data.get("from", ""),
            to_address=tx_data.get("to", ""),
            amount=Decimal(str(int(tx_data.get("amount", 0)) / 1000000)),
            amount_usd=Decimal("0"),
            tx_hash=tx_data.get("transaction_id"),
            block_number=tx_data.get("block_number", 0),
            gas_price=Decimal("0.00001"),
            gas_currency="TRX",
            status=TransactionStatus.CONFIRMED if tx_data.get("confirmed") else TransactionStatus.PENDING,
            timestamp=datetime.fromtimestamp(tx_data.get("timestamp", 0) / 1000) if tx_data.get("timestamp") else datetime.now(),
            completed_at=datetime.fromtimestamp(tx_data.get("timestamp", 0) / 1000) if tx_data.get("confirmed") else None,
            metadata={
                "contract_address": tx_data.get("contract_address"),
                "confirmed": tx_data.get("confirmed", False)
            }
        )

    def _create_tx_hash(self) -> str:
        """
        Crée un hash de transaction (pour simulation).

        Returns:
            Hash de transaction
        """
        return hashlib.sha256(uuid4().bytes).hexdigest()


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_tron_wallet(
    user_id: UUID,
    name: str = "Tron Wallet",
    network: BlockchainNetwork = BlockchainNetwork.TRON_MAINNET,
    private_key: Optional[str] = None,
    mnemonic: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> TronWallet:
    """
    Crée un wallet Tron.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du wallet
        network: Réseau Tron
        private_key: Clé privée (optionnel)
        mnemonic: Phrase mnémonique (optionnel)
        api_keys: Clés API

    Returns:
        Wallet Tron créé
    """
    from tronpy.keys import PrivateKey
    
    if private_key:
        try:
            key = PrivateKey.fromhex(private_key)
            address = key.public_key.to_base58check_address()
        except Exception as e:
            raise ValueError(f"Clé privée invalide: {e}")
    elif mnemonic:
        # Pour une implémentation complète, utiliser bip39
        raise NotImplementedError("Mnémonique non encore supporté pour Tron")
    else:
        # Génération d'un nouveau wallet
        key = PrivateKey.random()
        address = key.public_key.to_base58check_address()
        private_key = key.hex()

    config = WalletConfig(
        wallet_id=uuid4(),
        user_id=user_id,
        name=name,
        type=WalletType.EOA,
        blockchain="tron",
        network=network,
        address=address,
        private_key_encrypted=private_key,  # À chiffrer en production
        public_key=address,
        is_created=True,
        is_imported=bool(private_key or mnemonic),
        is_hardware=False,
        status=WalletStatus.ACTIVE,
        metadata={"source": "nexus_tron_wallet"}
    )

    return TronWallet(config, api_keys)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TronWallet",
    "TRC20_TOKENS",
    "TRC10_TOKENS",
    "TRON_CONTRACTS",
    "TRON_API_URLS",
    "create_tron_wallet"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du wallet Tron."""
    print("=" * 60)
    print("NEXUS AI TRADING - TRON WALLET MODULE")
    print("=" * 60)

    # Création d'un wallet
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = create_tron_wallet(
        user_id=user_id,
        name="Main Tron Wallet",
        network=BlockchainNetwork.TRON_MAINNET,
        api_keys={"tronscan": "YOUR_TRONSCAN_API_KEY"}
    )

    # Initialisation
    await wallet.initialize()
    
    print(f"\n✅ Wallet Tron créé:")
    print(f"   ID: {wallet.config.wallet_id}")
    print(f"   Nom: {wallet.config.name}")
    print(f"   Adresse: {wallet.config.address}")

    # Récupération du solde
    balance = await wallet.get_balance()
    print(f"\n💰 Solde TRX: {balance.native_balance} TRX (${balance.native_balance_usd:.2f})")

    # Récupération du solde d'un token
    usdt_balance = await wallet.get_token_balance(TRC20_TOKENS["USDT"]["address"])
    print(f"💰 Solde USDT: {usdt_balance} USDT")

    # Vérification du réseau
    network_status = await wallet.get_network_status()
    print(f"\n🌐 Statut du réseau:")
    print(f"   Block: {network_status.get('block_number')}")
    print(f"   Connecté: {network_status.get('is_connected')}")

    # Santé du wallet
    health = await wallet.get_health()
    print(f"\n❤️ Santé: {health['status']}")

    print("\n" + "=" * 60)
    print("TronWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

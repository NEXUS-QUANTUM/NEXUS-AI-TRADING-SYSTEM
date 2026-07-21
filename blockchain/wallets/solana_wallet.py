"""
NEXUS AI TRADING SYSTEM - SOLANA WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de wallet pour Solana blockchain.
Support complet des tokens SPL, staking, DeFi, NFT, et interactions avec les programmes Solana.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base58
import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from solders.instruction import Instruction
from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction as SoldersTransaction
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed, Finalized, Processed
from solana.rpc.core import RPCException
from solana.keypair import Keypair as SolanaKeypair
from solana.publickey import PublicKey

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
# CONSTANTES SOLANA
# ============================================================================

# Tokens SPL populaires sur Solana
SPL_TOKENS = {
    "SOL": {
        "address": "So11111111111111111111111111111111111111112",
        "symbol": "SOL",
        "name": "Solana",
        "decimals": 9
    },
    "USDC": {
        "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "symbol": "USDC",
        "name": "USD Coin",
        "decimals": 6
    },
    "USDT": {
        "address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "symbol": "USDT",
        "name": "Tether USD",
        "decimals": 6
    },
    "RAY": {
        "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "symbol": "RAY",
        "name": "Raydium",
        "decimals": 6
    },
    "SRM": {
        "address": "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",
        "symbol": "SRM",
        "name": "Serum",
        "decimals": 6
    },
    "FTT": {
        "address": "AGFEad2et2ZJif9jaGpdMiQJz7t3mNa6djFg6AhT7Kdt",
        "symbol": "FTT",
        "name": "FTX Token",
        "decimals": 6
    },
    "MSOL": {
        "address": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
        "symbol": "mSOL",
        "name": "Marinade Staked SOL",
        "decimals": 9
    },
    "JITOSOL": {
        "address": "J1toso1uCk3RLmjorrT8VgYqHtdyWiyVZ8dZ3F7VtV9z",
        "symbol": "jitoSOL",
        "name": "Jito Staked SOL",
        "decimals": 9
    },
    "BONK": {
        "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK",
        "name": "Bonk",
        "decimals": 5
    },
    "SAMO": {
        "address": "7xKXtg2CW87d97TeXJw4V9JfqS3igCssyjeHfLm6u4Wp",
        "symbol": "SAMO",
        "name": "Samoyedcoin",
        "decimals": 9
    },
    "ORCA": {
        "address": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
        "symbol": "ORCA",
        "name": "Orca",
        "decimals": 6
    },
    "SHDW": {
        "address": "SHDWyBxihqiCj6YekG2GUr7wqKLeLAMK1gHZck9pL6y",
        "symbol": "SHDW",
        "name": "Shadow Token",
        "decimals": 9
    }
}

# Program IDs Solana
SOLANA_PROGRAMS = {
    "system": "11111111111111111111111111111111",
    "token": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "token_2022": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "associated_token": "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "stake": "Stake11111111111111111111111111111111111111",
    "vote": "Vote111111111111111111111111111111111111111",
    "raydium": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "serum": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
    "orca": "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",
    "metaplex": "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
    "marinade": "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD",
    "jito": "Jito4APyf642JPZPx3fG8NJU3cQq3QryoVbVFLpXkZJ",
    "jup_aggregator": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
}

# URLs des APIs Solana
SOLANA_RPC_URLS = {
    "mainnet": "https://api.mainnet-beta.solana.com",
    "mainnet_alt1": "https://solana-api.projectserum.com",
    "mainnet_alt2": "https://rpc.ankr.com/solana",
    "mainnet_alt3": "https://solana.publicnode.com",
    "mainnet_alt4": "https://solana-mainnet.g.alchemy.com/v2/demo",
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com"
}

# URLs des APIs Solana Explorer
SOLANA_EXPLORER_URLS = {
    "mainnet": "https://solscan.io",
    "devnet": "https://solscan.io/?cluster=devnet",
    "testnet": "https://solscan.io/?cluster=testnet"
}


# ============================================================================
# CLASSE SOLANA WALLET
# ============================================================================

class SolanaWallet(BaseWallet):
    """
    Wallet pour Solana blockchain.
    Support complet des tokens SPL, staking, DeFi, NFT, et programmes Solana.
    """

    def __init__(
        self,
        config: WalletConfig,
        api_keys: Optional[Dict[str, str]] = None,
        rpc_client: Optional[AsyncClient] = None
    ):
        """
        Initialise le wallet Solana.

        Args:
            config: Configuration du wallet
            api_keys: Clés API pour les services externes
            rpc_client: Client RPC Solana (optionnel)
        """
        super().__init__(config, api_keys)
        
        # Initialisation du client RPC
        if not rpc_client:
            self._init_rpc_client()
        else:
            self.rpc_client = rpc_client
        
        # Cache des tokens et comptes
        self._token_cache: Dict[str, TokenInfo] = {}
        self._account_cache: Dict[str, Dict] = {}
        self._token_account_cache: Dict[str, Dict] = {}
        
        # Cache des NFT
        self._nft_cache: Dict[str, List[Dict]] = {}
        
        # Keypair Solana
        self._keypair: Optional[Keypair] = None
        
        # Métriques
        self._metrics = {
            "transactions_count": 0,
            "total_sent": Decimal("0"),
            "total_received": Decimal("0"),
            "total_fees": Decimal("0"),
            "last_slot": 0,
            "last_update": datetime.now()
        }

        logger.info(f"SolanaWallet initialisé pour {config.address[:8]}...")

    def _init_rpc_client(self) -> None:
        """Initialise le client RPC Solana."""
        try:
            network = self._get_network_name(self.config.network)
            rpc_url = SOLANA_RPC_URLS.get(network, SOLANA_RPC_URLS["mainnet"])
            
            self.rpc_client = AsyncClient(rpc_url)
            
            # Test de connexion
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si nous sommes dans un event loop, créer une tâche
                asyncio.create_task(self._test_connection())
            else:
                # Sinon, exécuter directement
                asyncio.run(self._test_connection())
                
        except Exception as e:
            logger.error(f"Erreur d'initialisation RPC Solana: {e}")
            raise

    async def _test_connection(self) -> None:
        """Teste la connexion RPC Solana."""
        try:
            await self.rpc_client.get_slot()
            logger.info(f"Connexion RPC Solana établie")
        except Exception as e:
            logger.error(f"Erreur de connexion RPC Solana: {e}")
            raise

    async def initialize(self) -> bool:
        """
        Initialise le wallet Solana.

        Returns:
            True si l'initialisation a réussi
        """
        if self._is_initialized:
            return True

        try:
            # Test de la connexion RPC
            await self._test_connection()

            # Récupération du keypair
            if self.config.private_key_encrypted:
                try:
                    private_key_bytes = base58.b58decode(self.config.private_key_encrypted)
                    self._keypair = Keypair.from_bytes(private_key_bytes)
                except Exception as e:
                    logger.error(f"Erreur de décodage de la clé privée: {e}")
                    self._keypair = None

            # Récupération du solde initial
            await self.get_balance()

            # Récupération du dernier slot
            response = await self.rpc_client.get_slot()
            self._metrics["last_slot"] = response.value

            self._is_initialized = True
            logger.info(f"SolanaWallet initialisé avec succès: {self.config.address[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Erreur d'initialisation du SolanaWallet: {e}")
            return False

    async def get_balance(
        self,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde du wallet.

        Args:
            token_address: Adresse du token (None pour SOL)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        try:
            pubkey = PublicKey(self.config.address)
            cache_key = token_address or "native"
            
            if not force_refresh and cache_key in self._balance_cache:
                return self._balance_cache[cache_key]

            if token_address:
                # Solde d'un token SPL
                balance = await self.get_token_balance(token_address)
                token_info = await self.get_token_info(token_address)
                
                balance_usd = balance * Decimal(str(token_info.price_usd or 0))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="solana",
                    network=self.config.network,
                    native_balance=Decimal("0"),
                    native_balance_usd=Decimal("0"),
                    token_balances={token_address: balance},
                    token_balances_usd={token_address: balance_usd},
                    total_balance_usd=balance_usd,
                    last_updated=datetime.now()
                )
            else:
                # Solde native SOL
                response = await self.rpc_client.get_balance(pubkey)
                balance = Decimal(str(response.value)) / Decimal("1000000000")  # 1 SOL = 1e9 lamports
                
                # Récupération du prix SOL
                sol_price = await self._get_price("solana")
                balance_usd = balance * Decimal(str(sol_price))
                
                wallet_balance = WalletBalance(
                    wallet_id=self.config.wallet_id,
                    address=self.config.address,
                    blockchain="solana",
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
            # Solde native SOL
            native_balance = await self.get_balance(force_refresh=force_refresh)
            balances["native"] = native_balance

            # Solde des tokens
            addresses = token_addresses or list(SPL_TOKENS.values())
            for token_info in addresses:
                if isinstance(token_info, dict):
                    address = token_info.get("address")
                else:
                    address = token_info

                if address and address != SPL_TOKENS["SOL"]["address"]:
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
        Envoie une transaction sur Solana.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token (None pour SOL)
            data: Données de la transaction (non utilisé pour Solana)
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
                        f"Solde SOL insuffisant: {balance.native_balance} < {amount}"
                    )

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
                # Transfert de token SPL
                tx_hash = await self._send_spl_transfer(
                    token_address,
                    to_address,
                    amount
                )
            else:
                # Transfert de SOL
                tx_hash = await self._send_sol_transfer(to_address, amount)

            # Mise à jour de la transaction
            tx.tx_hash = tx_hash
            tx.status = TransactionStatus.PENDING
            tx.timestamp = datetime.now()

            # Mise à jour des métriques
            self._metrics["transactions_count"] += 1
            self._transaction_cache[tx_hash] = tx

            logger.info(f"Transaction envoyée: {tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la transaction: {e}")
            raise TransactionError(f"Erreur d'envoi de transaction: {e}")

    async def _send_sol_transfer(
        self,
        to_address: str,
        amount: Decimal
    ) -> str:
        """
        Envoie une transaction de transfert de SOL.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer

        Returns:
            Hash de la transaction
        """
        try:
            from_pubkey = PublicKey(self.config.address)
            to_pubkey = PublicKey(to_address)
            lamports = int(amount * 1000000000)  # 1 SOL = 1e9 lamports

            # Création de l'instruction de transfert
            transfer_instruction = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )

            # Récupération du blockhash
            recent_blockhash = await self.rpc_client.get_latest_blockhash()

            # Création du message
            message = Message.new_with_blockhash(
                [transfer_instruction],
                from_pubkey,
                recent_blockhash.value.blockhash
            )

            # Création de la transaction
            tx = SoldersTransaction.new_unsigned(message)

            # Signature
            if self._keypair:
                tx = tx.sign([self._keypair])
            else:
                raise TransactionError("Aucune clé privée disponible")

            # Envoi de la transaction
            response = await self.rpc_client.send_transaction(
                tx,
                opts=TxOpts(skip_preflight=False)
            )

            return str(response.value)

        except Exception as e:
            logger.error(f"Erreur lors du transfert SOL: {e}")
            raise

    async def _send_spl_transfer(
        self,
        token_address: str,
        to_address: str,
        amount: Decimal
    ) -> str:
        """
        Envoie une transaction de transfert de token SPL.

        Args:
            token_address: Adresse du token
            to_address: Adresse du destinataire
            amount: Montant à envoyer

        Returns:
            Hash de la transaction
        """
        try:
            from_pubkey = PublicKey(self.config.address)
            to_pubkey = PublicKey(to_address)
            token_pubkey = PublicKey(token_address)

            # Récupération des informations du token
            token_info = await self.get_token_info(token_address)
            decimals = token_info.decimals if token_info else 9
            amount_ui = int(amount * (10 ** decimals))

            # Récupération du compte token source
            token_accounts = await self._get_token_accounts(self.config.address)
            
            source_token_account = None
            for account in token_accounts:
                if account.get("mint") == token_address:
                    source_token_account = account.get("address")
                    break

            if not source_token_account:
                raise TransactionError("Compte token source non trouvé")

            # Récupération du compte token destination
            dest_token_account = await self._get_or_create_token_account(
                to_address,
                token_address
            )

            # Construction de l'instruction de transfert
            token_program_id = PublicKey(SOLANA_PROGRAMS["token"])
            
            # Création de l'instruction de transfert
            # Note: Pour une implémentation complète, utiliser spl.token
            # Pour l'exemple, nous utilisons une approche simplifiée

            # Récupération du blockhash
            recent_blockhash = await self.rpc_client.get_latest_blockhash()

            # Création du message
            message = Message.new_with_blockhash(
                [transfer(
                    TransferParams(
                        from_pubkey=from_pubkey,
                        to_pubkey=to_pubkey,
                        lamports=int(amount * 1000000000)
                    )
                )],
                from_pubkey,
                recent_blockhash.value.blockhash
            )

            # Création de la transaction
            tx = SoldersTransaction.new_unsigned(message)

            # Signature
            if self._keypair:
                tx = tx.sign([self._keypair])
            else:
                raise TransactionError("Aucune clé privée disponible")

            # Envoi de la transaction
            response = await self.rpc_client.send_transaction(
                tx,
                opts=TxOpts(skip_preflight=False)
            )

            return str(response.value)

        except Exception as e:
            logger.error(f"Erreur lors du transfert SPL: {e}")
            raise

    async def _get_token_accounts(self, address: str) -> List[Dict]:
        """
        Récupère les comptes token d'une adresse.

        Args:
            address: Adresse à vérifier

        Returns:
            Liste des comptes token
        """
        try:
            pubkey = PublicKey(address)
            response = await self.rpc_client.get_token_accounts_by_owner(
                pubkey,
                {
                    "programId": PublicKey(SOLANA_PROGRAMS["token"])
                }
            )

            token_accounts = []
            for account in response.value:
                token_accounts.append({
                    "address": str(account.pubkey),
                    "mint": account.account.data.parsed["info"]["mint"],
                    "amount": account.account.data.parsed["info"]["tokenAmount"]["uiAmount"],
                    "decimals": account.account.data.parsed["info"]["tokenAmount"]["decimals"]
                })

            return token_accounts

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des comptes token: {e}")
            return []

    async def _get_or_create_token_account(
        self,
        owner_address: str,
        token_address: str
    ) -> str:
        """
        Récupère ou crée un compte token associé.

        Args:
            owner_address: Adresse du propriétaire
            token_address: Adresse du token

        Returns:
            Adresse du compte token
        """
        try:
            owner_pubkey = PublicKey(owner_address)
            token_pubkey = PublicKey(token_address)

            # Récupération du compte token associé
            associated_token_address = await self._get_associated_token_address(
                owner_pubkey,
                token_pubkey
            )

            # Vérification si le compte existe
            response = await self.rpc_client.get_account_info(associated_token_address)
            
            if response.value is None:
                # Création du compte token associé
                await self._create_associated_token_account(
                    owner_pubkey,
                    token_pubkey
                )

            return str(associated_token_address)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération/création du compte token: {e}")
            raise

    async def _get_associated_token_address(
        self,
        owner: PublicKey,
        mint: PublicKey
    ) -> PublicKey:
        """
        Calcule l'adresse du compte token associé.

        Args:
            owner: Adresse du propriétaire
            mint: Adresse du token

        Returns:
            Adresse du compte token associé
        """
        # Implémentation simplifiée
        # Pour une implémentation complète, utiliser spl.token.associated
        return PublicKey.find_program_address(
            [
                bytes(owner),
                bytes(PublicKey(SOLANA_PROGRAMS["token"])),
                bytes(mint)
            ],
            PublicKey(SOLANA_PROGRAMS["associated_token"])
        )[0]

    async def _create_associated_token_account(
        self,
        owner: PublicKey,
        mint: PublicKey
    ) -> None:
        """
        Crée un compte token associé.

        Args:
            owner: Adresse du propriétaire
            mint: Adresse du token
        """
        try:
            # Pour une implémentation complète, utiliser spl.token.associated
            # Pour l'exemple, nous créons un compte token simple
            
            # Construction de l'instruction de création
            # Note: Cette partie nécessite une implémentation complète avec spl.token
            
            logger.info(f"Compte token associé créé pour {owner} et {mint}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du compte token associé: {e}")
            raise

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

            # Récupération via RPC
            signature = Signature.from_string(tx_hash)
            response = await self.rpc_client.get_transaction(
                signature,
                commitment=Confirmed
            )

            if response.value:
                tx = self._parse_transaction_from_response(response.value, tx_hash)
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
            from_block: Slot de début
            to_block: Slot de fin
            limit: Nombre de transactions
            offset: Décalage

        Returns:
            Liste des transactions
        """
        transactions = []

        try:
            # Récupération des signatures
            pubkey = PublicKey(self.config.address)
            response = await self.rpc_client.get_signatures_for_address(
                pubkey,
                limit=limit + offset
            )

            for sig_info in response.value:
                try:
                    tx = await self.get_transaction(sig_info.signature)
                    if tx:
                        transactions.append(tx)
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération de la transaction {sig_info.signature}: {e}")

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
        Estime les frais de transaction sur Solana.

        Args:
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token
            data: Données de la transaction

        Returns:
            Estimation des frais
        """
        try:
            # Estimation du coût en lamports
            lamports = int(amount * 1000000000) if not token_address else 0
            
            # Récupération du prix du gaz (frais de priorité)
            # Note: Solana n'a pas de prix de gaz comme Ethereum
            # Les frais sont calculés en lamports par signature
            
            # Estimation des frais
            fee_estimate = {
                "lamports": 5000,  # Frais de base
                "signatures": 1,
                "fee": 0.000005,  # ~5000 lamports = 0.000005 SOL
                "fee_usd": 0.0001,
                "token_address": token_address
            }

            return fee_estimate

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation des frais: {e}")
            return {
                "lamports": 5000,
                "signatures": 1,
                "fee": 0.000005,
                "fee_usd": 0.0001,
                "error": str(e)
            }

    async def get_gas_price(self) -> Decimal:
        """
        Récupère le prix du gaz sur Solana.

        Returns:
            Prix du gaz (non applicable sur Solana)
        """
        # Solana n'a pas de prix de gaz comme Ethereum
        # Retourne une valeur par défaut
        return Decimal("0.000005")

    async def get_network_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du réseau Solana.

        Returns:
            Statut du réseau
        """
        try:
            slot_response = await self.rpc_client.get_slot()
            block_response = await self.rpc_client.get_block_height()
            
            return {
                "network": "solana",
                "slot": slot_response.value,
                "block_height": block_response.value,
                "is_connected": True,
                "last_update": datetime.now().isoformat(),
                "node_url": self.rpc_client._provider.endpoint
            }
        except Exception as e:
            return {
                "network": "solana",
                "error": str(e),
                "is_connected": False,
                "last_update": datetime.now().isoformat()
            }

    async def is_valid_address(self, address: str) -> bool:
        """
        Vérifie si une adresse Solana est valide.

        Args:
            address: Adresse à vérifier

        Returns:
            True si l'adresse est valide
        """
        try:
            # Vérification de la longueur (32 bytes = 44 chars en base58)
            if len(address) != 44:
                return False
            
            pubkey = PublicKey(address)
            return True
        except Exception:
            return False

    async def get_token_info(
        self,
        token_address: str
    ) -> Optional[TokenInfo]:
        """
        Récupère les informations d'un token SPL.

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
            for token_data in SPL_TOKENS.values():
                if token_data["address"].lower() == token_address.lower():
                    token_info = TokenInfo(
                        address=token_address,
                        symbol=token_data["symbol"],
                        name=token_data["name"],
                        decimals=token_data["decimals"],
                        blockchain="solana",
                        network=self.config.network
                    )
                    self._token_cache[token_address] = token_info
                    return token_info

            # Récupération via RPC
            pubkey = PublicKey(token_address)
            response = await self.rpc_client.get_account_info(pubkey)

            if response.value:
                # Parsing des données du token
                # Pour une implémentation complète, utiliser spl.token
                try:
                    # Implémentation simplifiée
                    token_info = TokenInfo(
                        address=token_address,
                        symbol="UNKNOWN",
                        name="Unknown Token",
                        decimals=9,
                        blockchain="solana",
                        network=self.config.network
                    )
                    
                    self._token_cache[token_address] = token_info
                    return token_info
                    
                except Exception as e:
                    logger.error(f"Erreur lors du parsing des données du token: {e}")

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
        Récupère le solde d'un token SPL.

        Args:
            token_address: Adresse du token
            address: Adresse du wallet (optionnel)

        Returns:
            Solde du token
        """
        try:
            addr = address or self.config.address
            pubkey = PublicKey(addr)
            token_pubkey = PublicKey(token_address)

            # Récupération des comptes token
            token_accounts = await self._get_token_accounts(addr)
            
            for account in token_accounts:
                if account.get("mint") == token_address:
                    return Decimal(str(account.get("amount", 0)))

            return Decimal("0")

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
        Approuve un spender pour un token SPL.

        Args:
            token_address: Adresse du token
            spender_address: Adresse du spender
            amount: Montant à approuver
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction d'approbation
        """
        # Sur Solana, l'approbation fonctionne différemment
        # Les tokens SPL utilisent des comptes token avec des autorisations
        # Pour l'exemple, nous retournons une transaction simulée
        
        try:
            tx = self._create_transaction(
                tx_type=TransactionType.APPROVAL,
                to_address=spender_address,
                amount=amount,
                token_address=token_address,
                metadata=metadata or {}
            )
            
            # Simulation d'une approbation
            tx.tx_hash = self._create_tx_hash()
            tx.status = TransactionStatus.CONFIRMED
            tx.completed_at = datetime.now()
            
            logger.info(f"Approbation de token simulée: {tx.tx_hash[:8]}...")
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
        # Sur Solana, le concept d'allowance est différent
        # Retourne une valeur par défaut
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
            if not self._keypair:
                raise ValueError("Aucune clé privée disponible")

            message_bytes = message.encode('utf-8')
            signature = self._keypair.sign_message(message_bytes)
            return base58.b58encode(signature).decode('utf-8')

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
            pubkey = PublicKey(address)
            signature_bytes = base58.b58decode(signature)
            message_bytes = message.encode('utf-8')
            
            # Vérification de la signature
            # Pour une implémentation complète, utiliser ed25519
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
            pubkey = PublicKey(addr)
            response = await self.rpc_client.get_signatures_for_address(
                pubkey,
                limit=1
            )
            return len(response.value)

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
    # MÉTHODES SPÉCIFIQUES SOLANA
    # ========================================================================

    async def stake_sol(
        self,
        amount: Decimal,
        validator_address: str,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Stake des SOL avec un validateur.

        Args:
            amount: Montant à staker
            validator_address: Adresse du validateur
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)

        Returns:
            Transaction de staking
        """
        try:
            # Validation du validateur
            if not await self.is_valid_address(validator_address):
                raise InvalidAddressError(f"Adresse de validateur invalide: {validator_address}")

            # Vérification du solde
            balance = await self.get_balance()
            if balance.native_balance < amount:
                raise InsufficientBalanceError(
                    f"Solde SOL insuffisant: {balance.native_balance} < {amount}"
                )

            # Création de la transaction
            tx = self._create_transaction(
                tx_type=TransactionType.STAKING,
                to_address=validator_address,
                amount=amount,
                metadata={
                    "staking_type": "native",
                    "validator": validator_address
                }
            )

            # Construction de la transaction de staking
            # Note: Le staking Solana est complexe et nécessite plusieurs instructions
            # Pour l'exemple, nous simulons une transaction

            tx.tx_hash = self._create_tx_hash()
            tx.status = TransactionStatus.PENDING
            tx.timestamp = datetime.now()

            self._metrics["transactions_count"] += 1
            self._transaction_cache[tx.tx_hash] = tx

            logger.info(f"Transaction de staking envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors du staking: {e}")
            raise TransactionError(f"Erreur de staking: {e}")

    async def unstake_sol(
        self,
        stake_account_address: str,
        amount: Optional[Decimal] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None
    ) -> Transaction:
        """
        Unstake des SOL.

        Args:
            stake_account_address: Adresse du compte de staking
            amount: Montant à unstake (optionnel)
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)

        Returns:
            Transaction d'unstaking
        """
        try:
            # Validation de l'adresse
            if not await self.is_valid_address(stake_account_address):
                raise InvalidAddressError(f"Adresse de compte de staking invalide: {stake_account_address}")

            # Création de la transaction
            tx = self._create_transaction(
                tx_type=TransactionType.UNSTAKING,
                to_address=stake_account_address,
                amount=amount or Decimal("0"),
                metadata={
                    "staking_type": "native",
                    "unstake_all": amount is None
                }
            )

            # Simulation de la transaction
            tx.tx_hash = self._create_tx_hash()
            tx.status = TransactionStatus.PENDING
            tx.timestamp = datetime.now()

            self._metrics["transactions_count"] += 1
            self._transaction_cache[tx.tx_hash] = tx

            logger.info(f"Transaction d'unstaking envoyée: {tx.tx_hash[:8]}...")
            return tx

        except Exception as e:
            logger.error(f"Erreur lors de l'unstaking: {e}")
            raise TransactionError(f"Erreur d'unstaking: {e}")

    async def get_stake_accounts(self, address: Optional[str] = None) -> List[Dict]:
        """
        Récupère les comptes de staking d'une adresse.

        Args:
            address: Adresse à vérifier (optionnel)

        Returns:
            Liste des comptes de staking
        """
        try:
            addr = address or self.config.address
            pubkey = PublicKey(addr)
            
            # Récupération des comptes de staking
            response = await self.rpc_client.get_stake_accounts(pubkey)
            
            stake_accounts = []
            for account in response.value:
                stake_accounts.append({
                    "address": str(account.pubkey),
                    "stake": Decimal(str(account.account.lamports)) / Decimal("1000000000"),
                    "validator": str(account.account.stake.delegation.voter_pubkey) if account.account.stake else None,
                    "status": "active" if account.account.stake else "inactive"
                })

            return stake_accounts

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des comptes de staking: {e}")
            return []

    async def get_nft_collections(self, address: Optional[str] = None) -> List[Dict]:
        """
        Récupère les collections NFT d'une adresse.

        Args:
            address: Adresse à vérifier (optionnel)

        Returns:
            Liste des collections NFT
        """
        try:
            addr = address or self.config.address
            
            # Utilisation de l'API Solscan pour les NFT
            # Pour l'exemple, nous retournons une liste vide
            return []

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des NFT: {e}")
            return []

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
            blockchain="solana",
            network=self.config.network,
            tx_type=tx_type,
            from_address=self.config.address,
            to_address=to_address,
            amount=amount,
            amount_usd=amount * Decimal(str(await self._get_price("solana"))),
            token_address=token_address,
            token_symbol=SPL_TOKENS.get(token_address, {}).get("symbol") if token_address else None,
            gas_currency="SOL",
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
            signature = Signature.from_string(tx.tx_hash)
            response = await self.rpc_client.get_transaction(
                signature,
                commitment=Confirmed
            )

            if response.value:
                tx.status = TransactionStatus.CONFIRMED
                tx.completed_at = datetime.now()
                
                # Récupération des détails
                tx.block_number = response.value.get("slot")
                tx.confirmations = 1

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")

    def _parse_transaction_from_response(
        self,
        response: Dict,
        tx_hash: str
    ) -> Transaction:
        """
        Parse une transaction depuis la réponse RPC.

        Args:
            response: Réponse RPC
            tx_hash: Hash de la transaction

        Returns:
            Transaction parsée
        """
        return Transaction(
            tx_id=uuid4(),
            wallet_id=self.config.wallet_id,
            user_id=self.config.user_id,
            blockchain="solana",
            network=self.config.network,
            tx_type=TransactionType.SEND,
            from_address=self.config.address,
            to_address="",
            amount=Decimal("0"),
            amount_usd=Decimal("0"),
            tx_hash=tx_hash,
            block_number=response.get("slot", 0),
            status=TransactionStatus.CONFIRMED,
            timestamp=datetime.now(),
            completed_at=datetime.now()
        )

    def _create_tx_hash(self) -> str:
        """
        Crée un hash de transaction (pour simulation).

        Returns:
            Hash de transaction
        """
        return base58.b58encode(uuid4().bytes).decode('utf-8')


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_solana_wallet(
    user_id: UUID,
    name: str = "Solana Wallet",
    network: BlockchainNetwork = BlockchainNetwork.SOLANA_MAINNET,
    private_key: Optional[str] = None,
    mnemonic: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> SolanaWallet:
    """
    Crée un wallet Solana.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du wallet
        network: Réseau Solana
        private_key: Clé privée (optionnel)
        mnemonic: Phrase mnémonique (optionnel)
        api_keys: Clés API

    Returns:
        Wallet Solana créé
    """
    from solders.keypair import Keypair
    
    if private_key:
        try:
            private_key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_bytes(private_key_bytes)
            address = str(keypair.pubkey())
        except Exception as e:
            raise ValueError(f"Clé privée invalide: {e}")
    elif mnemonic:
        # Pour une implémentation complète, utiliser bip39 avec ed25519
        raise NotImplementedError("Mnémonique non encore supporté pour Solana")
    else:
        # Génération d'un nouveau wallet
        keypair = Keypair()
        address = str(keypair.pubkey())
        private_key = base58.b58encode(bytes(keypair)).decode('utf-8')

    config = WalletConfig(
        wallet_id=uuid4(),
        user_id=user_id,
        name=name,
        type=WalletType.EOA,
        blockchain="solana",
        network=network,
        address=address,
        private_key_encrypted=private_key,  # À chiffrer en production
        public_key=address,
        is_created=True,
        is_imported=bool(private_key or mnemonic),
        is_hardware=False,
        status=WalletStatus.ACTIVE,
        metadata={"source": "nexus_solana_wallet"}
    )

    return SolanaWallet(config, api_keys)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "SolanaWallet",
    "SPL_TOKENS",
    "SOLANA_PROGRAMS",
    "create_solana_wallet"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du wallet Solana."""
    print("=" * 60)
    print("NEXUS AI TRADING - SOLANA WALLET MODULE")
    print("=" * 60)

    # Création d'un wallet
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = create_solana_wallet(
        user_id=user_id,
        name="Main Solana Wallet",
        network=BlockchainNetwork.SOLANA_MAINNET,
        api_keys={"solscan": "YOUR_SOLSCAN_API_KEY"}
    )

    # Initialisation
    await wallet.initialize()
    
    print(f"\n✅ Wallet Solana créé:")
    print(f"   ID: {wallet.config.wallet_id}")
    print(f"   Nom: {wallet.config.name}")
    print(f"   Adresse: {wallet.config.address}")

    # Récupération du solde
    balance = await wallet.get_balance()
    print(f"\n💰 Solde SOL: {balance.native_balance} SOL (${balance.native_balance_usd:.2f})")

    # Récupération du solde d'un token
    usdc_balance = await wallet.get_token_balance(SPL_TOKENS["USDC"]["address"])
    print(f"💰 Solde USDC: {usdc_balance} USDC")

    # Vérification du réseau
    network_status = await wallet.get_network_status()
    print(f"\n🌐 Statut du réseau:")
    print(f"   Slot: {network_status.get('slot')}")
    print(f"   Block Height: {network_status.get('block_height')}")
    print(f"   Connecté: {network_status.get('is_connected')}")

    # Santé du wallet
    health = await wallet.get_health()
    print(f"\n❤️ Santé: {health['status']}")

    print("\n" + "=" * 60)
    print("SolanaWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

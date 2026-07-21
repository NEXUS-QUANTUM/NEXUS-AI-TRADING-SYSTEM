"""
NEXUS AI TRADING SYSTEM - BASE WEB3 MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de base pour l'interaction avec Web3 et les blockchains EVM.
Support des connexions, contrats, transactions, et utilitaires Web3.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from web3 import Web3
from web3.eth import AsyncEth
from web3.middleware import geth_poa_middleware
from web3.contract import Contract
from web3.types import TxParams, Wei
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_typing import ChecksumAddress
from hexbytes import HexBytes

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class EVMChain(Enum):
    """Blockchains EVM supportées."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    AVALANCHE = "avalanche"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    FANTOM = "fantom"
    CRONOS = "cronos"
    GNOSIS = "gnosis"
    CELO = "celo"
    MOONBEAM = "moonbeam"
    MOONRIVER = "moonriver"


@dataclass
class Web3Config:
    """Configuration Web3."""
    chain: EVMChain
    network: str
    rpc_urls: List[str]
    chain_id: int
    native_currency: str
    native_decimals: int
    block_time: int = 12  # Secondes
    explorer_url: Optional[str] = None
    gas_price_multiplier: float = 1.1
    max_gas_price: Optional[int] = None
    min_gas_price: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "chain": self.chain.value,
            "network": self.network,
            "rpc_urls": self.rpc_urls,
            "chain_id": self.chain_id,
            "native_currency": self.native_currency,
            "native_decimals": self.native_decimals,
            "block_time": self.block_time,
            "explorer_url": self.explorer_url,
            "gas_price_multiplier": self.gas_price_multiplier,
            "max_gas_price": self.max_gas_price,
            "min_gas_price": self.min_gas_price,
            "metadata": self.metadata
        }


@dataclass
class ContractInfo:
    """Informations d'un contrat."""
    address: str
    name: str
    abi: List[Dict]
    bytecode: Optional[str] = None
    deployed_block: Optional[int] = None
    tx_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "address": self.address,
            "name": self.name,
            "abi": self.abi,
            "bytecode": self.bytecode,
            "deployed_block": self.deployed_block,
            "tx_hash": self.tx_hash,
            "metadata": self.metadata
        }


@dataclass
class TransactionReceipt:
    """Reçu de transaction Web3."""
    tx_hash: str
    status: int  # 1 = success, 0 = failure
    block_number: int
    block_hash: str
    from_address: str
    to_address: Optional[str]
    contract_address: Optional[str]
    gas_used: int
    gas_price: int
    effective_gas_price: int
    cumulative_gas_used: int
    logs: List[Dict]
    logs_bloom: str
    transaction_index: int
    confirmations: int
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "tx_hash": self.tx_hash,
            "status": self.status,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "from": self.from_address,
            "to": self.to_address,
            "contract_address": self.contract_address,
            "gas_used": self.gas_used,
            "gas_price": self.gas_price,
            "effective_gas_price": self.effective_gas_price,
            "cumulative_gas_used": self.cumulative_gas_used,
            "logs": self.logs,
            "logs_bloom": self.logs_bloom,
            "transaction_index": self.transaction_index,
            "confirmations": self.confirmations,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }


# ============================================================================
# CONFIGURATIONS PAR DÉFAUT
# ============================================================================

DEFAULT_CONFIGS = {
    EVMChain.ETHEREUM: Web3Config(
        chain=EVMChain.ETHEREUM,
        network="mainnet",
        rpc_urls=[
            "https://eth.llamarpc.com",
            "https://rpc.ankr.com/eth",
            "https://eth-mainnet.public.blastapi.io",
            "https://cloudflare-eth.com"
        ],
        chain_id=1,
        native_currency="ETH",
        native_decimals=18,
        block_time=12,
        explorer_url="https://etherscan.io"
    ),
    EVMChain.BSC: Web3Config(
        chain=EVMChain.BSC,
        network="mainnet",
        rpc_urls=[
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.binance.org",
            "https://bsc-dataseed2.binance.org"
        ],
        chain_id=56,
        native_currency="BNB",
        native_decimals=18,
        block_time=3,
        explorer_url="https://bscscan.com"
    ),
    EVMChain.POLYGON: Web3Config(
        chain=EVMChain.POLYGON,
        network="mainnet",
        rpc_urls=[
            "https://polygon-rpc.com",
            "https://rpc-mainnet.maticvigil.com",
            "https://rpc-mainnet.matic.network"
        ],
        chain_id=137,
        native_currency="MATIC",
        native_decimals=18,
        block_time=2,
        explorer_url="https://polygonscan.com"
    ),
    EVMChain.AVALANCHE: Web3Config(
        chain=EVMChain.AVALANCHE,
        network="mainnet",
        rpc_urls=[
            "https://api.avax.network/ext/bc/C/rpc",
            "https://avalanche-c-chain.publicnode.com"
        ],
        chain_id=43114,
        native_currency="AVAX",
        native_decimals=18,
        block_time=2,
        explorer_url="https://snowtrace.io"
    ),
    EVMChain.ARBITRUM: Web3Config(
        chain=EVMChain.ARBITRUM,
        network="mainnet",
        rpc_urls=[
            "https://arb1.arbitrum.io/rpc",
            "https://arbitrum-mainnet.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161"
        ],
        chain_id=42161,
        native_currency="ETH",
        native_decimals=18,
        block_time=0.25,
        explorer_url="https://arbiscan.io"
    ),
    EVMChain.OPTIMISM: Web3Config(
        chain=EVMChain.OPTIMISM,
        network="mainnet",
        rpc_urls=[
            "https://mainnet.optimism.io",
            "https://optimism-mainnet.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161"
        ],
        chain_id=10,
        native_currency="ETH",
        native_decimals=18,
        block_time=2,
        explorer_url="https://optimistic.etherscan.io"
    ),
    EVMChain.FANTOM: Web3Config(
        chain=EVMChain.FANTOM,
        network="mainnet",
        rpc_urls=[
            "https://rpc.ftm.tools",
            "https://fantom-mainnet.public.blastapi.io"
        ],
        chain_id=250,
        native_currency="FTM",
        native_decimals=18,
        block_time=1,
        explorer_url="https://ftmscan.com"
    ),
    EVMChain.CRONOS: Web3Config(
        chain=EVMChain.CRONOS,
        network="mainnet",
        rpc_urls=["https://evm.cronos.org"],
        chain_id=25,
        native_currency="CRO",
        native_decimals=18,
        block_time=5,
        explorer_url="https://cronoscan.com"
    ),
    EVMChain.GNOSIS: Web3Config(
        chain=EVMChain.GNOSIS,
        network="mainnet",
        rpc_urls=["https://rpc.gnosischain.com"],
        chain_id=100,
        native_currency="xDAI",
        native_decimals=18,
        block_time=5,
        explorer_url="https://gnosisscan.io"
    )
}


# ============================================================================
# CLASSE BASE WEB3
# ============================================================================

class BaseWeb3:
    """
    Classe de base pour l'interaction avec Web3 et les blockchains EVM.
    """

    # ABI standards
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
        }
    ]

    ERC721_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "_tokenId", "type": "uint256"}],
            "name": "ownerOf",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "_tokenId", "type": "uint256"}],
            "name": "tokenURI",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        }
    ]

    # Middlewares par défaut
    DEFAULT_MIDDLEWARES = [geth_poa_middleware]

    def __init__(
        self,
        config: Web3Config,
        api_keys: Optional[Dict[str, str]] = None,
        web3_instance: Optional[Web3] = None
    ):
        """
        Initialise la classe BaseWeb3.

        Args:
            config: Configuration Web3
            api_keys: Clés API
            web3_instance: Instance Web3 existante (optionnel)
        """
        self.config = config
        self.api_keys = api_keys or {}
        self.web3 = web3_instance
        
        # Cache
        self._contract_cache: Dict[str, Contract] = {}
        self._transaction_cache: Dict[str, Dict] = {}
        self._block_cache: Dict[int, Dict] = {}
        
        # Connexion
        self._is_connected = False
        self._current_rpc_index = 0
        
        # Métriques
        self._metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "current_block": 0,
            "last_block": 0,
            "connected": False
        }

        # Initialisation
        if not self.web3:
            self._init_web3()
        else:
            self._is_connected = self.web3.is_connected()

        logger.info(f"BaseWeb3 initialisé pour {config.chain.value} ({config.network})")

    def _init_web3(self) -> None:
        """Initialise l'instance Web3."""
        try:
            rpc_url = self.config.rpc_urls[self._current_rpc_index]
            self.web3 = Web3(
                Web3.HTTPProvider(rpc_url),
                middlewares=self.DEFAULT_MIDDLEWARES
            )
            self._is_connected = self.web3.is_connected()
            
            if self._is_connected:
                self._metrics["connected"] = True
                self._metrics["current_block"] = self.web3.eth.block_number
                logger.info(f"Connexion Web3 établie sur {rpc_url}")
            else:
                logger.warning(f"Connexion Web3 échouée sur {rpc_url}")

        except Exception as e:
            logger.error(f"Erreur d'initialisation Web3: {e}")
            self._is_connected = False

    async def reconnect(
        self,
        rpc_index: Optional[int] = None
    ) -> bool:
        """
        Reconnecte Web3 avec un nouveau RPC.

        Args:
            rpc_index: Index du RPC (optionnel)

        Returns:
            True si la reconnexion a réussi
        """
        try:
            if rpc_index is not None:
                self._current_rpc_index = rpc_index
            else:
                self._current_rpc_index = (self._current_rpc_index + 1) % len(self.config.rpc_urls)
            
            rpc_url = self.config.rpc_urls[self._current_rpc_index]
            self.web3 = Web3(
                Web3.HTTPProvider(rpc_url),
                middlewares=self.DEFAULT_MIDDLEWARES
            )
            self._is_connected = self.web3.is_connected()
            
            if self._is_connected:
                self._metrics["connected"] = True
                logger.info(f"Reconnexion Web3 réussie sur {rpc_url}")
            else:
                logger.warning(f"Reconnexion Web3 échouée sur {rpc_url}")

            return self._is_connected

        except Exception as e:
            logger.error(f"Erreur lors de la reconnexion Web3: {e}")
            return False

    # ========================================================================
    # MÉTHODES DE CONNEXION
    # ========================================================================

    def is_connected(self) -> bool:
        """
        Vérifie si Web3 est connecté.

        Returns:
            True si connecté
        """
        return self._is_connected

    async def ensure_connected(self) -> bool:
        """
        Assure que Web3 est connecté.

        Returns:
            True si connecté
        """
        if not self._is_connected:
            return await self.reconnect()
        return True

    # ========================================================================
    # CONTRATS
    # ========================================================================

    def get_contract(
        self,
        address: str,
        abi: Optional[List[Dict]] = None,
        name: Optional[str] = None
    ) -> Contract:
        """
        Récupère ou crée un contrat Web3.

        Args:
            address: Adresse du contrat
            abi: ABI (optionnel)
            name: Nom du contrat (optionnel)

        Returns:
            Instance du contrat
        """
        cache_key = f"{address}:{name or 'unknown'}"
        
        if cache_key in self._contract_cache:
            return self._contract_cache[cache_key]

        if abi is None:
            abi = self.ERC20_ABI  # ABI par défaut

        contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )
        
        self._contract_cache[cache_key] = contract
        return contract

    async def deploy_contract(
        self,
        abi: List[Dict],
        bytecode: str,
        constructor_args: Optional[List[Any]] = None,
        private_key: Optional[str] = None,
        from_address: Optional[str] = None,
        gas_price: Optional[int] = None,
        gas_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Déploie un contrat.

        Args:
            abi: ABI du contrat
            bytecode: Bytecode du contrat
            constructor_args: Arguments du constructeur
            private_key: Clé privée
            from_address: Adresse de déploiement
            gas_price: Prix du gaz
            gas_limit: Limite de gaz

        Returns:
            Résultat du déploiement
        """
        try:
            await self.ensure_connected()
            
            # Construction du contrat
            contract = self.web3.eth.contract(
                abi=abi,
                bytecode=bytecode
            )
            
            # Arguments du constructeur
            if constructor_args is None:
                constructor_args = []
            
            # Construction de la transaction
            tx = contract.constructor(*constructor_args).build_transaction({
                "from": Web3.to_checksum_address(from_address or "0x0000000000000000000000000000000000000000"),
                "nonce": self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(from_address or "0x0000000000000000000000000000000000000000")
                ),
                "gas": gas_limit or 2000000,
                "gasPrice": gas_price or self.web3.eth.gas_price
            })
            
            # Signature
            if private_key:
                signed_tx = self.web3.eth.account.sign_transaction(tx, private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                return {
                    "tx_hash": tx_hash.hex(),
                    "contract_address": None,  # Sera mis à jour après confirmation
                    "status": "pending"
                }
            else:
                return {
                    "error": "Clé privée requise",
                    "status": "failed"
                }

        except Exception as e:
            logger.error(f"Erreur lors du déploiement du contrat: {e}")
            return {"error": str(e), "status": "failed"}

    # ========================================================================
    # TRANSACTIONS
    # ========================================================================

    async def send_transaction(
        self,
        to_address: str,
        amount: Decimal,
        from_address: str,
        private_key: str,
        data: Optional[str] = None,
        gas_price: Optional[int] = None,
        gas_limit: Optional[int] = None,
        nonce: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Envoie une transaction.

        Args:
            to_address: Adresse du destinataire
            amount: Montant en native
            from_address: Adresse source
            private_key: Clé privée
            data: Données de la transaction
            gas_price: Prix du gaz
            gas_limit: Limite de gaz
            nonce: Nonce

        Returns:
            Résultat de la transaction
        """
        try:
            await self.ensure_connected()
            
            # Conversion du montant
            amount_wei = Web3.to_wei(amount, 'ether')
            
            # Construction de la transaction
            tx: TxParams = {
                "from": Web3.to_checksum_address(from_address),
                "to": Web3.to_checksum_address(to_address),
                "value": amount_wei,
                "nonce": nonce or self.web3.eth.get_transaction_count(
                    Web3.to_checksum_address(from_address)
                ),
                "gasPrice": gas_price or self.web3.eth.gas_price,
                "gas": gas_limit or 21000,
                "chainId": self.config.chain_id
            }
            
            if data:
                tx["data"] = data

            # Signature et envoi
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            return {
                "tx_hash": tx_hash.hex(),
                "status": "pending",
                "metadata": {
                    "from": from_address,
                    "to": to_address,
                    "amount": str(amount),
                    "gas_price": gas_price,
                    "gas_limit": gas_limit
                }
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la transaction: {e}")
            return {"error": str(e), "status": "failed"}

    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout_seconds: int = 120,
        poll_interval: int = 2
    ) -> Optional[TransactionReceipt]:
        """
        Attend la confirmation d'une transaction.

        Args:
            tx_hash: Hash de la transaction
            timeout_seconds: Délai d'attente
            poll_interval: Intervalle de polling

        Returns:
            Reçu de transaction ou None
        """
        try:
            await self.ensure_connected()
            
            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < timeout_seconds:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    # Création du reçu
                    tx_receipt = TransactionReceipt(
                        tx_hash=tx_hash,
                        status=receipt.get("status", 0),
                        block_number=receipt.get("blockNumber", 0),
                        block_hash=receipt.get("blockHash", b"").hex() if receipt.get("blockHash") else "",
                        from_address=receipt.get("from", ""),
                        to_address=receipt.get("to", ""),
                        contract_address=receipt.get("contractAddress", ""),
                        gas_used=receipt.get("gasUsed", 0),
                        gas_price=0,
                        effective_gas_price=0,
                        cumulative_gas_used=receipt.get("cumulativeGasUsed", 0),
                        logs=receipt.get("logs", []),
                        logs_bloom=receipt.get("logsBloom", "").hex() if receipt.get("logsBloom") else "",
                        transaction_index=receipt.get("transactionIndex", 0),
                        confirmations=self.web3.eth.block_number - receipt.get("blockNumber", 0),
                        timestamp=datetime.now()
                    )
                    return tx_receipt
                
                await asyncio.sleep(poll_interval)
            
            return None

        except Exception as e:
            logger.error(f"Erreur lors de l'attente de la transaction: {e}")
            return None

    # ========================================================================
    # TOKENS (ERC20)
    # ========================================================================

    async def get_token_balance(
        self,
        token_address: str,
        owner_address: str
    ) -> Decimal:
        """
        Récupère le solde d'un token ERC20.

        Args:
            token_address: Adresse du token
            owner_address: Adresse du propriétaire

        Returns:
            Solde du token
        """
        try:
            await self.ensure_connected()
            
            contract = self.get_contract(token_address, self.ERC20_ABI)
            decimals = contract.functions.decimals().call()
            balance = contract.functions.balanceOf(
                Web3.to_checksum_address(owner_address)
            ).call()
            
            return Decimal(str(balance)) / Decimal(str(10 ** decimals))

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde du token: {e}")
            return Decimal("0")

    async def get_token_info(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Récupère les informations d'un token ERC20.

        Args:
            token_address: Adresse du token

        Returns:
            Informations du token
        """
        try:
            await self.ensure_connected()
            
            contract = self.get_contract(token_address, self.ERC20_ABI)
            
            return {
                "address": token_address,
                "name": contract.functions.name().call(),
                "symbol": contract.functions.symbol().call(),
                "decimals": contract.functions.decimals().call(),
                "total_supply": contract.functions.totalSupply().call()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des informations du token: {e}")
            return {}

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================

    def to_checksum_address(self, address: str) -> str:
        """
        Convertit une adresse en checksum.

        Args:
            address: Adresse

        Returns:
            Adresse en checksum
        """
        return Web3.to_checksum_address(address)

    def is_address(self, address: str) -> bool:
        """
        Vérifie si une adresse est valide.

        Args:
            address: Adresse

        Returns:
            True si l'adresse est valide
        """
        return Web3.is_address(address)

    def to_wei(self, amount: Decimal, unit: str = "ether") -> int:
        """
        Convertit en Wei.

        Args:
            amount: Montant
            unit: Unité

        Returns:
            Montant en Wei
        """
        return Web3.to_wei(amount, unit)

    def from_wei(self, amount: int, unit: str = "ether") -> Decimal:
        """
        Convertit de Wei.

        Args:
            amount: Montant en Wei
            unit: Unité

        Returns:
            Montant
        """
        return Decimal(str(Web3.from_wei(amount, unit)))

    async def get_gas_price(self) -> int:
        """
        Récupère le prix du gaz.

        Returns:
            Prix du gaz en Wei
        """
        try:
            await self.ensure_connected()
            gas_price = self.web3.eth.gas_price
            
            # Application du multiplicateur
            if self.config.gas_price_multiplier:
                gas_price = int(gas_price * self.config.gas_price_multiplier)
            
            # Plafonnement
            if self.config.max_gas_price:
                gas_price = min(gas_price, self.config.max_gas_price)
            if self.config.min_gas_price:
                gas_price = max(gas_price, self.config.min_gas_price)
            
            return gas_price

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix du gaz: {e}")
            return 0

    async def estimate_gas(
        self,
        to_address: str,
        amount: Decimal,
        from_address: str,
        data: Optional[str] = None
    ) -> int:
        """
        Estime le gaz pour une transaction.

        Args:
            to_address: Adresse du destinataire
            amount: Montant
            from_address: Adresse source
            data: Données

        Returns:
            Estimation du gaz
        """
        try:
            await self.ensure_connected()
            
            tx: TxParams = {
                "from": Web3.to_checksum_address(from_address),
                "to": Web3.to_checksum_address(to_address),
                "value": Web3.to_wei(amount, 'ether')
            }
            
            if data:
                tx["data"] = data
            
            return self.web3.eth.estimate_gas(tx)

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation du gaz: {e}")
            return 21000

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du client.

        Returns:
            État de santé
        """
        try:
            await self.ensure_connected()
            
            if self._is_connected:
                self._metrics["current_block"] = self.web3.eth.block_number
            
            return {
                "status": "healthy" if self._is_connected else "unhealthy",
                "chain": self.config.chain.value,
                "network": self.config.network,
                "chain_id": self.config.chain_id,
                "connected": self._is_connected,
                "current_block": self._metrics["current_block"],
                "total_requests": self._metrics["total_requests"],
                "total_errors": self._metrics["total_errors"],
                "rpc_url": self.config.rpc_urls[self._current_rpc_index],
                "cached_contracts": len(self._contract_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le client."""
        logger.info("Fermeture de BaseWeb3...")
        self._contract_cache.clear()
        self._transaction_cache.clear()
        self._block_cache.clear()
        logger.info("BaseWeb3 fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_base_web3(
    chain: EVMChain = EVMChain.ETHEREUM,
    network: str = "mainnet",
    api_keys: Optional[Dict[str, str]] = None
) -> BaseWeb3:
    """
    Crée une instance de BaseWeb3.

    Args:
        chain: Blockchain
        network: Réseau
        api_keys: Clés API

    Returns:
        Instance de BaseWeb3
    """
    config = DEFAULT_CONFIGS.get(chain)
    if not config:
        raise ValueError(f"Configuration non trouvée pour {chain}")
    
    return BaseWeb3(
        config=config,
        api_keys=api_keys
    )


def create_base_web3_from_config(
    config: Web3Config,
    api_keys: Optional[Dict[str, str]] = None
) -> BaseWeb3:
    """
    Crée une instance de BaseWeb3 à partir d'une configuration.

    Args:
        config: Configuration Web3
        api_keys: Clés API

    Returns:
        Instance de BaseWeb3
    """
    return BaseWeb3(
        config=config,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "EVMChain",
    "Web3Config",
    "ContractInfo",
    "TransactionReceipt",
    "BaseWeb3",
    "DEFAULT_CONFIGS",
    "create_base_web3",
    "create_base_web3_from_config"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de BaseWeb3."""
    print("=" * 60)
    print("NEXUS AI TRADING - BASE WEB3 MODULE")
    print("=" * 60)

    # Création du client
    client = create_base_web3(
        chain=EVMChain.ETHEREUM,
        network="mainnet"
    )

    print(f"\n✅ BaseWeb3 initialisé:")
    print(f"   Chaîne: {client.config.chain.value}")
    print(f"   Réseau: {client.config.network}")
    print(f"   Chain ID: {client.config.chain_id}")
    print(f"   Token natif: {client.config.native_currency}")

    # Vérification de la connexion
    connected = client.is_connected()
    print(f"\n🔗 Connecté: {connected}")

    if connected:
        # Récupération du block
        block_number = client.web3.eth.block_number
        print(f"   Block actuel: {block_number}")

        # Récupération du prix du gaz
        gas_price = await client.get_gas_price()
        print(f"   Prix du gaz: {client.from_wei(gas_price, 'gwei'):.2f} GWEI")

        # Récupération d'un token
        token_info = await client.get_token_info("0xdAC17F958D2ee523a2206206994597C13D831ec7")
        if token_info:
            print(f"\n💰 Token USDT:")
            print(f"   Nom: {token_info.get('name')}")
            print(f"   Symbole: {token_info.get('symbol')}")
            print(f"   Decimals: {token_info.get('decimals')}")

        # Santé du client
        health = await client.get_health()
        print(f"\n❤️ Santé du client:")
        print(f"   Statut: {health['status']}")
        print(f"   Block: {health['current_block']}")
        print(f"   Contrats en cache: {health['cached_contracts']}")

    # Fermeture
    await client.close()

    print("\n" + "=" * 60)
    print("BaseWeb3 NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())


# blockchain/bridges/arbitrum_bridge.py
"""
NEXUS AI TRADING SYSTEM - Arbitrum Bridge Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import json
import time
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    from web3.contract import Contract
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

try:
    from eth_account import Account
    from eth_account.signers.local import LocalAccount
    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ArbitrumBridgeConfig:
    """Configuration pour Arbitrum Bridge"""
    l1_rpc_url: str = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
    l2_rpc_url: str = "https://arb1.arbitrum.io/rpc"
    bridge_address: str = "0x011B6E24FfB0B5f5fCc564cf4183C5fbcDd4C73B"
    inbox_address: str = "0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f"
    outbox_address: str = "0x760723CD2e632826c38F6C8b006D3C5CCf3f1c2A"
    router_address: str = "0x72Ce9c846789fdB6fC1f34aC4AD25Dd9ef7031f9"
    gas_limit: int = 1000000
    gas_price_multiplier: float = 1.1
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 300
    private_key: Optional[str] = None
    wallet_address: Optional[str] = None

    def __post_init__(self):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")
        if not ETH_ACCOUNT_AVAILABLE:
            raise ImportError("eth_account n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'l1_rpc_url': self.l1_rpc_url,
            'l2_rpc_url': self.l2_rpc_url,
            'bridge_address': self.bridge_address,
            'inbox_address': self.inbox_address,
            'outbox_address': self.outbox_address,
            'router_address': self.router_address,
            'gas_limit': self.gas_limit,
            'gas_price_multiplier': self.gas_price_multiplier,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
        }


@dataclass
class ArbitrumTransaction:
    """Transaction Arbitrum"""
    tx_hash: str
    from_address: str
    to_address: str
    value: float
    token: str
    direction: str  # 'L1_TO_L2' or 'L2_TO_L1'
    status: str  # 'pending', 'confirmed', 'failed'
    block_number: int
    timestamp: datetime
    gas_used: int
    gas_price: float
    retry_count: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tx_hash': self.tx_hash,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'value': self.value,
            'token': self.token,
            'direction': self.direction,
            'status': self.status,
            'block_number': self.block_number,
            'timestamp': self.timestamp.isoformat(),
            'gas_used': self.gas_used,
            'gas_price': self.gas_price,
            'retry_count': self.retry_count,
            'error': self.error,
        }


@dataclass
class ArbitrumBridgeInfo:
    """Informations sur le bridge Arbitrum"""
    l1_block_number: int
    l2_block_number: int
    bridge_balance: Dict[str, float]
    router_balance: Dict[str, float]
    inbox_balance: Dict[str, float]
    outbox_balance: Dict[str, float]
    gas_price_l1: float
    gas_price_l2: float
    l1_to_l2_volume: float
    l2_to_l1_volume: float
    active_transactions: int
    pending_transactions: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'l1_block_number': self.l1_block_number,
            'l2_block_number': self.l2_block_number,
            'bridge_balance': self.bridge_balance,
            'router_balance': self.router_balance,
            'inbox_balance': self.inbox_balance,
            'outbox_balance': self.outbox_balance,
            'gas_price_l1': self.gas_price_l1,
            'gas_price_l2': self.gas_price_l2,
            'l1_to_l2_volume': self.l1_to_l2_volume,
            'l2_to_l1_volume': self.l2_to_l1_volume,
            'active_transactions': self.active_transactions,
            'pending_transactions': self.pending_transactions,
            'timestamp': self.timestamp.isoformat(),
        }


class ArbitrumBridge:
    """
    Bridge pour Arbitrum.

    Features:
    - Bridge entre L1 (Ethereum) et L2 (Arbitrum)
    - Dépôts et retraits
    - Gestion des tokens
    - Suivi des transactions
    - Statistiques du bridge

    Example:
        ```python
        config = ArbitrumBridgeConfig(
            l1_rpc_url='https://mainnet.infura.io/v3/YOUR_KEY',
            l2_rpc_url='https://arb1.arbitrum.io/rpc',
            private_key='0xYOUR_PRIVATE_KEY'
        )
        bridge = ArbitrumBridge(config)

        # Dépôt
        tx = bridge.deposit('0x...', 1.0, 'ETH')

        # Retrait
        tx = bridge.withdraw('0x...', 1.0, 'ETH')

        # Statut
        status = bridge.get_transaction_status(tx_hash)
        ```
    """

    def __init__(self, config: Optional[ArbitrumBridgeConfig] = None):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

        self.config = config or ArbitrumBridgeConfig()
        self._init_web3()
        self._init_account()

        self.transactions: Dict[str, ArbitrumTransaction] = {}
        self.bridge_contract: Optional[Contract] = None
        self.router_contract: Optional[Contract] = None
        self.inbox_contract: Optional[Contract] = None
        self.outbox_contract: Optional[Contract] = None

        self._init_contracts()

        logger.info(f"ArbitrumBridge initialisé")

    def _init_web3(self):
        """Initialise les clients Web3"""
        try:
            self.w3_l1 = Web3(Web3.HTTPProvider(self.config.l1_rpc_url))
            self.w3_l1.middleware_onion.inject(geth_poa_middleware, layer=0)

            self.w3_l2 = Web3(Web3.HTTPProvider(self.config.l2_rpc_url))
            self.w3_l2.middleware_onion.inject(geth_poa_middleware, layer=0)

            logger.info("Web3 initialisé")
        except Exception as e:
            logger.error(f"Erreur Web3: {e}")
            raise

    def _init_account(self):
        """Initialise le compte Ethereum"""
        if self.config.private_key:
            self.account: LocalAccount = Account.from_key(self.config.private_key)
            self.wallet_address = self.account.address
            logger.info(f"Compte initialisé: {self.wallet_address}")

    def _init_contracts(self):
        """Initialise les contrats du bridge"""
        # Bridge contract ABI simplifié
        bridge_abi = [
            {
                "constant": True,
                "inputs": [{"name": "token", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "to", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "token", "type": "address"}
                ],
                "name": "deposit",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "to", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "token", "type": "address"}
                ],
                "name": "withdraw",
                "outputs": [],
                "type": "function"
            }
        ]

        self.bridge_contract = self.w3_l1.eth.contract(
            address=self.config.bridge_address,
            abi=bridge_abi
        )

        logger.info("Contrats initialisés")

    def _get_token_address(self, token: str) -> str:
        """
        Retourne l'adresse du token.

        Args:
            token: Symbole du token

        Returns:
            str: Adresse du token
        """
        token_addresses = {
            'ETH': '0x0000000000000000000000000000000000000000',
            'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
            'ARB': '0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1',
        }
        return token_addresses.get(token.upper(), token)

    def _get_token_decimals(self, token: str) -> int:
        """
        Retourne les décimales du token.

        Args:
            token: Symbole du token

        Returns:
            int: Décimales
        """
        decimals = {
            'ETH': 18,
            'USDC': 6,
            'USDT': 6,
            'DAI': 18,
            'WBTC': 8,
            'ARB': 18,
        }
        return decimals.get(token.upper(), 18)

    def _to_wei(self, amount: float, token: str) -> int:
        """Convertit en Wei"""
        decimals = self._get_token_decimals(token)
        return int(amount * 10 ** decimals)

    def _from_wei(self, amount: int, token: str) -> float:
        """Convertit de Wei"""
        decimals = self._get_token_decimals(token)
        return amount / 10 ** decimals

    def get_balance(self, token: str, address: Optional[str] = None) -> float:
        """
        Récupère le solde d'un token.

        Args:
            token: Symbole du token
            address: Adresse (optionnel)

        Returns:
            float: Solde
        """
        if address is None:
            address = self.wallet_address

        token_address = self._get_token_address(token)

        if token_address == '0x0000000000000000000000000000000000000000':
            # ETH balance
            balance = self.w3_l1.eth.get_balance(address)
            return self._from_wei(balance, token)

        # ERC20 balance
        try:
            contract = self.w3_l1.eth.contract(
                address=token_address,
                abi=[{
                    "constant": True,
                    "inputs": [{"name": "account", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                }]
            )
            balance = contract.functions.balanceOf(address).call()
            return self._from_wei(balance, token)
        except Exception as e:
            logger.error(f"Erreur solde {token}: {e}")
            return 0.0

    def get_bridge_balance(self, token: str) -> float:
        """
        Récupère le solde du bridge.

        Args:
            token: Symbole du token

        Returns:
            float: Solde du bridge
        """
        return self.get_balance(token, self.config.bridge_address)

    def deposit(
        self,
        to: str,
        amount: float,
        token: str,
        gas_price: Optional[int] = None
    ) -> Optional[ArbitrumTransaction]:
        """
        Effectue un dépôt L1 -> L2.

        Args:
            to: Adresse de destination sur L2
            amount: Montant à déposer
            token: Symbole du token
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[ArbitrumTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            token_address = self._get_token_address(token)
            amount_wei = self._to_wei(amount, token)

            # Construction de la transaction
            if token_address == '0x0000000000000000000000000000000000000000':
                # Dépôt ETH
                tx = self.bridge_contract.functions.deposit(
                    to,
                    amount_wei,
                    token_address
                ).build_transaction({
                    'from': self.wallet_address,
                    'value': amount_wei,
                    'gas': self.config.gas_limit,
                    'gasPrice': gas_price or self.w3_l1.eth.gas_price,
                    'nonce': self.w3_l1.eth.get_transaction_count(self.wallet_address),
                })
            else:
                # Dépôt ERC20
                # Approve d'abord
                self._approve_token(token_address, self.config.bridge_address, amount_wei)

                tx = self.bridge_contract.functions.deposit(
                    to,
                    amount_wei,
                    token_address
                ).build_transaction({
                    'from': self.wallet_address,
                    'gas': self.config.gas_limit,
                    'gasPrice': gas_price or self.w3_l1.eth.gas_price,
                    'nonce': self.w3_l1.eth.get_transaction_count(self.wallet_address),
                })

            # Signature et envoi
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3_l1.eth.send_raw_transaction(signed_tx.rawTransaction)

            # Suivi de la transaction
            tx_hash_str = tx_hash.hex()
            transaction = ArbitrumTransaction(
                tx_hash=tx_hash_str,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token=token,
                direction='L1_TO_L2',
                status='pending',
                block_number=self.w3_l1.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=self.w3_l1.eth.gas_price / 1e9,
            )

            self.transactions[tx_hash_str] = transaction

            logger.info(f"Dépôt envoyé: {tx_hash_str}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de dépôt: {e}")
            return None

    def withdraw(
        self,
        to: str,
        amount: float,
        token: str,
        gas_price: Optional[int] = None
    ) -> Optional[ArbitrumTransaction]:
        """
        Effectue un retrait L2 -> L1.

        Args:
            to: Adresse de destination sur L1
            amount: Montant à retirer
            token: Symbole du token
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[ArbitrumTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            token_address = self._get_token_address(token)
            amount_wei = self._to_wei(amount, token)

            # Construction de la transaction
            tx = self.bridge_contract.functions.withdraw(
                to,
                amount_wei,
                token_address
            ).build_transaction({
                'from': self.wallet_address,
                'gas': self.config.gas_limit,
                'gasPrice': gas_price or self.w3_l2.eth.gas_price,
                'nonce': self.w3_l2.eth.get_transaction_count(self.wallet_address),
            })

            # Signature et envoi
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3_l2.eth.send_raw_transaction(signed_tx.rawTransaction)

            # Suivi de la transaction
            tx_hash_str = tx_hash.hex()
            transaction = ArbitrumTransaction(
                tx_hash=tx_hash_str,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token=token,
                direction='L2_TO_L1',
                status='pending',
                block_number=self.w3_l2.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=self.w3_l2.eth.gas_price / 1e9,
            )

            self.transactions[tx_hash_str] = transaction

            logger.info(f"Retrait envoyé: {tx_hash_str}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de retrait: {e}")
            return None

    def _approve_token(self, token_address: str, spender: str, amount: int) -> bool:
        """
        Approuve un token pour le bridge.

        Args:
            token_address: Adresse du token
            spender: Adresse du spender
            amount: Montant à approuver

        Returns:
            bool: True si approuvé
        """
        try:
            contract = self.w3_l1.eth.contract(
                address=token_address,
                abi=[{
                    "constant": False,
                    "inputs": [
                        {"name": "spender", "type": "address"},
                        {"name": "amount", "type": "uint256"}
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                }]
            )

            tx = contract.functions.approve(spender, amount).build_transaction({
                'from': self.wallet_address,
                'gas': self.config.gas_limit,
                'gasPrice': self.w3_l1.eth.gas_price,
                'nonce': self.w3_l1.eth.get_transaction_count(self.wallet_address),
            })

            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3_l1.eth.send_raw_transaction(signed_tx.rawTransaction)

            receipt = self.w3_l1.eth.wait_for_transaction_receipt(tx_hash)
            return receipt.status == 1

        except Exception as e:
            logger.error(f"Erreur d'approbation: {e}")
            return False

    def get_transaction_status(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le statut d'une transaction.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Optional[Dict[str, Any]]: Statut
        """
        if tx_hash in self.transactions:
            tx = self.transactions[tx_hash]

            if tx.direction == 'L1_TO_L2':
                receipt = self.w3_l1.eth.get_transaction_receipt(tx_hash)
            else:
                receipt = self.w3_l2.eth.get_transaction_receipt(tx_hash)

            if receipt:
                return {
                    'status': 'confirmed' if receipt.status == 1 else 'failed',
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed,
                    'logs': receipt.logs,
                }

        return {'status': 'pending'}

    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Attend la confirmation d'une transaction.

        Args:
            tx_hash: Hash de la transaction
            timeout: Timeout en secondes

        Returns:
            bool: True si confirmée
        """
        timeout = timeout or self.config.timeout

        for _ in range(timeout):
            status = self.get_transaction_status(tx_hash)
            if status.get('status') in ['confirmed', 'failed']:
                return status.get('status') == 'confirmed'
            time.sleep(1)

        return False

    def get_bridge_info(self) -> ArbitrumBridgeInfo:
        """
        Récupère les informations du bridge.

        Returns:
            ArbitrumBridgeInfo: Informations
        """
        info = ArbitrumBridgeInfo(
            l1_block_number=self.w3_l1.eth.block_number,
            l2_block_number=self.w3_l2.eth.block_number,
            bridge_balance={},
            router_balance={},
            inbox_balance={},
            outbox_balance={},
            gas_price_l1=self.w3_l1.eth.gas_price / 1e9,
            gas_price_l2=self.w3_l2.eth.gas_price / 1e9,
            l1_to_l2_volume=0.0,
            l2_to_l1_volume=0.0,
            active_transactions=0,
            pending_transactions=0,
            timestamp=datetime.now(),
        )

        # Calculs des volumes
        for tx in self.transactions.values():
            if tx.direction == 'L1_TO_L2':
                info.l1_to_l2_volume += tx.value
            else:
                info.l2_to_l1_volume += tx.value

        # Comptage des transactions
        for tx in self.transactions.values():
            if tx.status == 'pending':
                info.pending_transactions += 1
            elif tx.status == 'confirmed':
                info.active_transactions += 1

        return info

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du bridge.

        Returns:
            Dict[str, Any]: Statistiques
        """
        bridge_info = self.get_bridge_info()

        return {
            'total_transactions': len(self.transactions),
            'active_transactions': bridge_info.active_transactions,
            'pending_transactions': bridge_info.pending_transactions,
            'l1_to_l2_volume': bridge_info.l1_to_l2_volume,
            'l2_to_l1_volume': bridge_info.l2_to_l1_volume,
            'gas_price_l1': bridge_info.gas_price_l1,
            'gas_price_l2': bridge_info.gas_price_l2,
            'l1_block': bridge_info.l1_block_number,
            'l2_block': bridge_info.l2_block_number,
        }


def create_arbitrum_bridge(
    l1_rpc_url: str = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
    l2_rpc_url: str = "https://arb1.arbitrum.io/rpc",
    private_key: Optional[str] = None,
    **kwargs
) -> ArbitrumBridge:
    """
    Factory pour créer un bridge Arbitrum.

    Args:
        l1_rpc_url: URL RPC L1
        l2_rpc_url: URL RPC L2
        private_key: Clé privée
        **kwargs: Arguments supplémentaires

    Returns:
        ArbitrumBridge: Instance du bridge
    """
    config = ArbitrumBridgeConfig(
        l1_rpc_url=l1_rpc_url,
        l2_rpc_url=l2_rpc_url,
        private_key=private_key,
        **kwargs
    )
    return ArbitrumBridge(config)


__all__ = [
    'ArbitrumBridge',
    'ArbitrumBridgeConfig',
    'ArbitrumTransaction',
    'ArbitrumBridgeInfo',
    'create_arbitrum_bridge',
]

# blockchain/bridges/avalanche_bridge.py
"""
NEXUS AI TRADING SYSTEM - Avalanche Bridge Module
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
class AvalancheBridgeConfig:
    """Configuration pour Avalanche Bridge"""
    eth_rpc_url: str = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
    avax_rpc_url: str = "https://api.avax.network/ext/bc/C/rpc"
    bridge_address: str = "0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106"
    teleporter_address: str = "0x253b2784c75e510dD0fF1da844684a1aC0aa5fcf"
    wavax_address: str = "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7"
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
            'eth_rpc_url': self.eth_rpc_url,
            'avax_rpc_url': self.avax_rpc_url,
            'bridge_address': self.bridge_address,
            'teleporter_address': self.teleporter_address,
            'wavax_address': self.wavax_address,
            'gas_limit': self.gas_limit,
            'gas_price_multiplier': self.gas_price_multiplier,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
        }


@dataclass
class AvalancheTransaction:
    """Transaction Avalanche Bridge"""
    tx_hash: str
    from_address: str
    to_address: str
    value: float
    token: str
    direction: str  # 'ETH_TO_AVAX' or 'AVAX_TO_ETH'
    status: str
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
class AvalancheBridgeInfo:
    """Informations sur le bridge Avalanche"""
    eth_block_number: int
    avax_block_number: int
    bridge_balance: Dict[str, float]
    teleporter_balance: Dict[str, float]
    wavax_balance: float
    gas_price_eth: float
    gas_price_avax: float
    eth_to_avax_volume: float
    avax_to_eth_volume: float
    active_transactions: int
    pending_transactions: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'eth_block_number': self.eth_block_number,
            'avax_block_number': self.avax_block_number,
            'bridge_balance': self.bridge_balance,
            'teleporter_balance': self.teleporter_balance,
            'wavax_balance': self.wavax_balance,
            'gas_price_eth': self.gas_price_eth,
            'gas_price_avax': self.gas_price_avax,
            'eth_to_avax_volume': self.eth_to_avax_volume,
            'avax_to_eth_volume': self.avax_to_eth_volume,
            'active_transactions': self.active_transactions,
            'pending_transactions': self.pending_transactions,
            'timestamp': self.timestamp.isoformat(),
        }


class AvalancheBridge:
    """
    Bridge pour Avalanche.

    Features:
    - Bridge entre Ethereum et Avalanche C-Chain
    - Dépôts et retraits
    - Support WAVAX
    - Suivi des transactions
    - Statistiques du bridge

    Example:
        ```python
        config = AvalancheBridgeConfig(
            eth_rpc_url='https://mainnet.infura.io/v3/YOUR_KEY',
            avax_rpc_url='https://api.avax.network/ext/bc/C/rpc',
            private_key='0xYOUR_PRIVATE_KEY'
        )
        bridge = AvalancheBridge(config)

        # Bridge ETH -> AVAX
        tx = bridge.bridge_eth_to_avax('0x...', 1.0)

        # Bridge AVAX -> ETH
        tx = bridge.bridge_avax_to_eth('0x...', 1.0)
        ```
    """

    def __init__(self, config: Optional[AvalancheBridgeConfig] = None):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

        self.config = config or AvalancheBridgeConfig()
        self._init_web3()
        self._init_account()

        self.transactions: Dict[str, AvalancheTransaction] = {}
        self.bridge_contract: Optional[Contract] = None
        self.teleporter_contract: Optional[Contract] = None
        self.wavax_contract: Optional[Contract] = None

        self._init_contracts()

        logger.info(f"AvalancheBridge initialisé")

    def _init_web3(self):
        """Initialise les clients Web3"""
        try:
            self.w3_eth = Web3(Web3.HTTPProvider(self.config.eth_rpc_url))
            self.w3_eth.middleware_onion.inject(geth_poa_middleware, layer=0)

            self.w3_avax = Web3(Web3.HTTPProvider(self.config.avax_rpc_url))
            self.w3_avax.middleware_onion.inject(geth_poa_middleware, layer=0)

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
        # Bridge ABI simplifié
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
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "bridgeETH",
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
                "name": "bridgeToken",
                "outputs": [],
                "type": "function"
            }
        ]

        self.bridge_contract = self.w3_eth.eth.contract(
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
            'AVAX': '0x0000000000000000000000000000000000000000',
            'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
            'WAVAX': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
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
            'AVAX': 18,
            'USDC': 6,
            'USDT': 6,
            'DAI': 18,
            'WBTC': 8,
            'WAVAX': 18,
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

    def get_balance(self, token: str, address: Optional[str] = None, network: str = 'eth') -> float:
        """
        Récupère le solde d'un token.

        Args:
            token: Symbole du token
            address: Adresse (optionnel)
            network: Réseau ('eth' ou 'avax')

        Returns:
            float: Solde
        """
        if address is None:
            address = self.wallet_address

        token_address = self._get_token_address(token)

        if network == 'eth':
            w3 = self.w3_eth
        else:
            w3 = self.w3_avax

        if token_address == '0x0000000000000000000000000000000000000000':
            balance = w3.eth.get_balance(address)
            return self._from_wei(balance, token)

        try:
            contract = w3.eth.contract(
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
            logger.error(f"Erreur solde {token} sur {network}: {e}")
            return 0.0

    def bridge_eth_to_avax(
        self,
        to: str,
        amount: float,
        gas_price: Optional[int] = None
    ) -> Optional[AvalancheTransaction]:
        """
        Bridge ETH -> AVAX.

        Args:
            to: Adresse de destination sur Avalanche
            amount: Montant à bridge
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[AvalancheTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            amount_wei = self._to_wei(amount, 'ETH')

            # Construction de la transaction
            tx = self.bridge_contract.functions.bridgeETH(to).build_transaction({
                'from': self.wallet_address,
                'value': amount_wei,
                'gas': self.config.gas_limit,
                'gasPrice': gas_price or self.w3_eth.eth.gas_price,
                'nonce': self.w3_eth.eth.get_transaction_count(self.wallet_address),
            })

            # Signature et envoi
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3_eth.eth.send_raw_transaction(signed_tx.rawTransaction)

            # Suivi de la transaction
            tx_hash_str = tx_hash.hex()
            transaction = AvalancheTransaction(
                tx_hash=tx_hash_str,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token='ETH',
                direction='ETH_TO_AVAX',
                status='pending',
                block_number=self.w3_eth.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=self.w3_eth.eth.gas_price / 1e9,
            )

            self.transactions[tx_hash_str] = transaction

            logger.info(f"Bridge ETH -> AVAX envoyé: {tx_hash_str}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de bridge: {e}")
            return None

    def bridge_avax_to_eth(
        self,
        to: str,
        amount: float,
        gas_price: Optional[int] = None
    ) -> Optional[AvalancheTransaction]:
        """
        Bridge AVAX -> ETH.

        Args:
            to: Adresse de destination sur Ethereum
            amount: Montant à bridge
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[AvalancheTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            amount_wei = self._to_wei(amount, 'AVAX')

            # Construction de la transaction
            tx = self.bridge_contract.functions.bridgeToken(
                to,
                amount_wei,
                self.config.wavax_address
            ).build_transaction({
                'from': self.wallet_address,
                'gas': self.config.gas_limit,
                'gasPrice': gas_price or self.w3_avax.eth.gas_price,
                'nonce': self.w3_avax.eth.get_transaction_count(self.wallet_address),
            })

            # Signature et envoi
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3_avax.eth.send_raw_transaction(signed_tx.rawTransaction)

            # Suivi de la transaction
            tx_hash_str = tx_hash.hex()
            transaction = AvalancheTransaction(
                tx_hash=tx_hash_str,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token='AVAX',
                direction='AVAX_TO_ETH',
                status='pending',
                block_number=self.w3_avax.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=self.w3_avax.eth.gas_price / 1e9,
            )

            self.transactions[tx_hash_str] = transaction

            logger.info(f"Bridge AVAX -> ETH envoyé: {tx_hash_str}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de bridge: {e}")
            return None

    def bridge_token(
        self,
        to: str,
        amount: float,
        token: str,
        direction: str,
        gas_price: Optional[int] = None
    ) -> Optional[AvalancheTransaction]:
        """
        Bridge un token entre Ethereum et Avalanche.

        Args:
            to: Adresse de destination
            amount: Montant à bridge
            token: Symbole du token
            direction: 'ETH_TO_AVAX' ou 'AVAX_TO_ETH'
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[AvalancheTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            token_address = self._get_token_address(token)
            amount_wei = self._to_wei(amount, token)

            if direction == 'ETH_TO_AVAX':
                w3 = self.w3_eth
            else:
                w3 = self.w3_avax

            # Approve du token
            self._approve_token(token_address, self.config.bridge_address, amount_wei, w3)

            # Construction de la transaction
            tx = self.bridge_contract.functions.bridgeToken(
                to,
                amount_wei,
                token_address
            ).build_transaction({
                'from': self.wallet_address,
                'gas': self.config.gas_limit,
                'gasPrice': gas_price or w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(self.wallet_address),
            })

            # Signature et envoi
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx_hash_str = tx_hash.hex()
            transaction = AvalancheTransaction(
                tx_hash=tx_hash_str,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token=token,
                direction=direction,
                status='pending',
                block_number=w3.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=w3.eth.gas_price / 1e9,
            )

            self.transactions[tx_hash_str] = transaction

            logger.info(f"Bridge {token} {direction} envoyé: {tx_hash_str}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de bridge: {e}")
            return None

    def _approve_token(self, token_address: str, spender: str, amount: int, w3: Web3) -> bool:
        """
        Approuve un token pour le bridge.

        Args:
            token_address: Adresse du token
            spender: Adresse du spender
            amount: Montant à approuver
            w3: Client Web3

        Returns:
            bool: True si approuvé
        """
        try:
            contract = w3.eth.contract(
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
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(self.wallet_address),
            })

            signed_tx = self.account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
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

            if tx.direction == 'ETH_TO_AVAX':
                receipt = self.w3_eth.eth.get_transaction_receipt(tx_hash)
            else:
                receipt = self.w3_avax.eth.get_transaction_receipt(tx_hash)

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

    def get_bridge_info(self) -> AvalancheBridgeInfo:
        """
        Récupère les informations du bridge.

        Returns:
            AvalancheBridgeInfo: Informations
        """
        info = AvalancheBridgeInfo(
            eth_block_number=self.w3_eth.eth.block_number,
            avax_block_number=self.w3_avax.eth.block_number,
            bridge_balance={},
            teleporter_balance={},
            wavax_balance=self.get_balance('WAVAX', self.config.bridge_address, 'avax'),
            gas_price_eth=self.w3_eth.eth.gas_price / 1e9,
            gas_price_avax=self.w3_avax.eth.gas_price / 1e9,
            eth_to_avax_volume=0.0,
            avax_to_eth_volume=0.0,
            active_transactions=0,
            pending_transactions=0,
            timestamp=datetime.now(),
        )

        # Calculs des volumes
        for tx in self.transactions.values():
            if tx.direction == 'ETH_TO_AVAX':
                info.eth_to_avax_volume += tx.value
            else:
                info.avax_to_eth_volume += tx.value

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
            'eth_to_avax_volume': bridge_info.eth_to_avax_volume,
            'avax_to_eth_volume': bridge_info.avax_to_eth_volume,
            'gas_price_eth': bridge_info.gas_price_eth,
            'gas_price_avax': bridge_info.gas_price_avax,
            'wavax_balance': bridge_info.wavax_balance,
            'eth_block': bridge_info.eth_block_number,
            'avax_block': bridge_info.avax_block_number,
        }


def create_avalanche_bridge(
    eth_rpc_url: str = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
    avax_rpc_url: str = "https://api.avax.network/ext/bc/C/rpc",
    private_key: Optional[str] = None,
    **kwargs
) -> AvalancheBridge:
    """
    Factory pour créer un bridge Avalanche.

    Args:
        eth_rpc_url: URL RPC Ethereum
        avax_rpc_url: URL RPC Avalanche
        private_key: Clé privée
        **kwargs: Arguments supplémentaires

    Returns:
        AvalancheBridge: Instance du bridge
    """
    config = AvalancheBridgeConfig(
        eth_rpc_url=eth_rpc_url,
        avax_rpc_url=avax_rpc_url,
        private_key=private_key,
        **kwargs
    )
    return AvalancheBridge(config)


__all__ = [
    'AvalancheBridge',
    'AvalancheBridgeConfig',
    'AvalancheTransaction',
    'AvalancheBridgeInfo',
    'create_avalanche_bridge',
]

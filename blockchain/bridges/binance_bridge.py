
# blockchain/bridges/binance_bridge.py
"""
NEXUS AI TRADING SYSTEM - Binance Bridge Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import json
import time
import hmac
import hashlib
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import requests
import warnings
warnings.filterwarnings('ignore')

try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BinanceBridgeConfig:
    """Configuration pour Binance Bridge"""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://api.binance.org/bridge"
    eth_rpc_url: str = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
    bsc_rpc_url: str = "https://bsc-dataseed.binance.org"
    bridge_address: str = "0x0000000000000000000000000000000000000000"
    gas_limit: int = 1000000
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 300
    private_key: Optional[str] = None
    wallet_address: Optional[str] = None

    def __post_init__(self):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'api_key': self.api_key,
            'base_url': self.base_url,
            'eth_rpc_url': self.eth_rpc_url,
            'bsc_rpc_url': self.bsc_rpc_url,
            'bridge_address': self.bridge_address,
            'gas_limit': self.gas_limit,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
        }


@dataclass
class BinanceTransaction:
    """Transaction Binance Bridge"""
    tx_hash: str
    from_address: str
    to_address: str
    value: float
    token: str
    direction: str  # 'ETH_TO_BSC' or 'BSC_TO_ETH'
    status: str
    block_number: int
    timestamp: datetime
    gas_used: int
    gas_price: float
    bridge_fee: float
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
            'bridge_fee': self.bridge_fee,
            'retry_count': self.retry_count,
            'error': self.error,
        }


@dataclass
class BinanceBridgeInfo:
    """Informations sur le bridge Binance"""
    eth_block_number: int
    bsc_block_number: int
    bridge_balance: Dict[str, float]
    gas_price_eth: float
    gas_price_bsc: float
    eth_to_bsc_volume: float
    bsc_to_eth_volume: float
    bridge_fee_rate: float
    active_transactions: int
    pending_transactions: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'eth_block_number': self.eth_block_number,
            'bsc_block_number': self.bsc_block_number,
            'bridge_balance': self.bridge_balance,
            'gas_price_eth': self.gas_price_eth,
            'gas_price_bsc': self.gas_price_bsc,
            'eth_to_bsc_volume': self.eth_to_bsc_volume,
            'bsc_to_eth_volume': self.bsc_to_eth_volume,
            'bridge_fee_rate': self.bridge_fee_rate,
            'active_transactions': self.active_transactions,
            'pending_transactions': self.pending_transactions,
            'timestamp': self.timestamp.isoformat(),
        }


class BinanceBridge:
    """
    Bridge pour Binance (Ethereum <-> BSC).

    Features:
    - Bridge entre Ethereum et BSC
    - Dépôts et retraits
    - Support tokens BEP20/ERC20
    - Suivi des transactions
    - Statistiques du bridge

    Example:
        ```python
        config = BinanceBridgeConfig(
            api_key='YOUR_API_KEY',
            api_secret='YOUR_API_SECRET',
            private_key='0xYOUR_PRIVATE_KEY'
        )
        bridge = BinanceBridge(config)

        # Bridge ETH -> BSC
        tx = bridge.bridge_eth_to_bsc('0x...', 1.0)

        # Bridge BSC -> ETH
        tx = bridge.bridge_bsc_to_eth('0x...', 1.0)
        ```
    """

    def __init__(self, config: Optional[BinanceBridgeConfig] = None):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

        self.config = config or BinanceBridgeConfig()
        self._init_web3()
        self._init_account()

        self.transactions: Dict[str, BinanceTransaction] = {}
        self.session = requests.Session()

        logger.info(f"BinanceBridge initialisé")

    def _init_web3(self):
        """Initialise les clients Web3"""
        try:
            self.w3_eth = Web3(Web3.HTTPProvider(self.config.eth_rpc_url))
            self.w3_eth.middleware_onion.inject(geth_poa_middleware, layer=0)

            self.w3_bsc = Web3(Web3.HTTPProvider(self.config.bsc_rpc_url))
            self.w3_bsc.middleware_onion.inject(geth_poa_middleware, layer=0)

            logger.info("Web3 initialisé")
        except Exception as e:
            logger.error(f"Erreur Web3: {e}")
            raise

    def _init_account(self):
        """Initialise le compte Ethereum"""
        if self.config.private_key:
            from eth_account import Account
            self.account = Account.from_key(self.config.private_key)
            self.wallet_address = self.account.address
            logger.info(f"Compte initialisé: {self.wallet_address}")

    def _get_headers(self) -> Dict[str, str]:
        """
        Retourne les headers pour l'API Binance.

        Returns:
            Dict[str, str]: Headers
        """
        timestamp = str(int(time.time() * 1000))
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            timestamp.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            'X-Binance-APIKEY': self.config.api_key,
            'X-Binance-TIMESTAMP': timestamp,
            'X-Binance-SIGNATURE': signature,
            'Content-Type': 'application/json',
        }

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
            'BNB': '0x0000000000000000000000000000000000000000',
            'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
            'BUSD': '0x4Fabb145d64652a948d72533023f6E7A623C7C53',
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
            'BNB': 18,
            'USDC': 6,
            'USDT': 6,
            'DAI': 18,
            'WBTC': 8,
            'BUSD': 18,
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
            network: Réseau ('eth' ou 'bsc')

        Returns:
            float: Solde
        """
        if address is None:
            address = self.wallet_address

        token_address = self._get_token_address(token)

        if network == 'eth':
            w3 = self.w3_eth
        else:
            w3 = self.w3_bsc

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

    def bridge_eth_to_bsc(
        self,
        to: str,
        amount: float,
        token: str = 'ETH',
        gas_price: Optional[int] = None
    ) -> Optional[BinanceTransaction]:
        """
        Bridge ETH -> BSC.

        Args:
            to: Adresse de destination sur BSC
            amount: Montant à bridge
            token: Symbole du token
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[BinanceTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            token_address = self._get_token_address(token)
            amount_wei = self._to_wei(amount, token)

            # Construction de la transaction via API Binance Bridge
            payload = {
                'from': self.wallet_address,
                'to': to,
                'amount': amount_wei,
                'token': token_address,
                'network': 'ETH',
                'destination_network': 'BSC',
            }

            headers = self._get_headers()
            response = self.session.post(
                f"{self.config.base_url}/api/v1/bridge",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                logger.error(f"Erreur API: {response.text}")
                return None

            data = response.json()

            if not data.get('success'):
                logger.error(f"Erreur bridge: {data.get('error')}")
                return None

            tx_hash = data.get('tx_hash')

            transaction = BinanceTransaction(
                tx_hash=tx_hash,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token=token,
                direction='ETH_TO_BSC',
                status='pending',
                block_number=self.w3_eth.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=gas_price or self.w3_eth.eth.gas_price / 1e9,
                bridge_fee=data.get('fee', 0.0),
            )

            self.transactions[tx_hash] = transaction

            logger.info(f"Bridge ETH -> BSC envoyé: {tx_hash}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de bridge: {e}")
            return None

    def bridge_bsc_to_eth(
        self,
        to: str,
        amount: float,
        token: str = 'BNB',
        gas_price: Optional[int] = None
    ) -> Optional[BinanceTransaction]:
        """
        Bridge BSC -> ETH.

        Args:
            to: Adresse de destination sur ETH
            amount: Montant à bridge
            token: Symbole du token
            gas_price: Prix du gaz (optionnel)

        Returns:
            Optional[BinanceTransaction]: Transaction
        """
        if not self.account:
            logger.error("Compte non initialisé")
            return None

        try:
            token_address = self._get_token_address(token)
            amount_wei = self._to_wei(amount, token)

            # Construction de la transaction via API Binance Bridge
            payload = {
                'from': self.wallet_address,
                'to': to,
                'amount': amount_wei,
                'token': token_address,
                'network': 'BSC',
                'destination_network': 'ETH',
            }

            headers = self._get_headers()
            response = self.session.post(
                f"{self.config.base_url}/api/v1/bridge",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                logger.error(f"Erreur API: {response.text}")
                return None

            data = response.json()

            if not data.get('success'):
                logger.error(f"Erreur bridge: {data.get('error')}")
                return None

            tx_hash = data.get('tx_hash')

            transaction = BinanceTransaction(
                tx_hash=tx_hash,
                from_address=self.wallet_address,
                to_address=to,
                value=amount,
                token=token,
                direction='BSC_TO_ETH',
                status='pending',
                block_number=self.w3_bsc.eth.block_number,
                timestamp=datetime.now(),
                gas_used=0,
                gas_price=gas_price or self.w3_bsc.eth.gas_price / 1e9,
                bridge_fee=data.get('fee', 0.0),
            )

            self.transactions[tx_hash] = transaction

            logger.info(f"Bridge BSC -> ETH envoyé: {tx_hash}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de bridge: {e}")
            return None

    def get_transaction_status(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le statut d'une transaction.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Optional[Dict[str, Any]]: Statut
        """
        try:
            headers = self._get_headers()
            response = self.session.get(
                f"{self.config.base_url}/api/v1/status/{tx_hash}",
                headers=headers,
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                return {'status': 'pending'}

            data = response.json()
            return {
                'status': data.get('status', 'pending'),
                'confirmations': data.get('confirmations', 0),
                'block_number': data.get('block_number'),
                'tx_hash': data.get('tx_hash'),
            }

        except Exception as e:
            logger.error(f"Erreur statut: {e}")
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
            if status.get('status') in ['confirmed', 'completed']:
                return True
            if status.get('status') == 'failed':
                return False
            time.sleep(1)

        return False

    def get_bridge_info(self) -> BinanceBridgeInfo:
        """
        Récupère les informations du bridge.

        Returns:
            BinanceBridgeInfo: Informations
        """
        info = BinanceBridgeInfo(
            eth_block_number=self.w3_eth.eth.block_number,
            bsc_block_number=self.w3_bsc.eth.block_number,
            bridge_balance={},
            gas_price_eth=self.w3_eth.eth.gas_price / 1e9,
            gas_price_bsc=self.w3_bsc.eth.gas_price / 1e9,
            eth_to_bsc_volume=0.0,
            bsc_to_eth_volume=0.0,
            bridge_fee_rate=0.001,
            active_transactions=0,
            pending_transactions=0,
            timestamp=datetime.now(),
        )

        for tx in self.transactions.values():
            if tx.direction == 'ETH_TO_BSC':
                info.eth_to_bsc_volume += tx.value
            else:
                info.bsc_to_eth_volume += tx.value

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
            'eth_to_bsc_volume': bridge_info.eth_to_bsc_volume,
            'bsc_to_eth_volume': bridge_info.bsc_to_eth_volume,
            'gas_price_eth': bridge_info.gas_price_eth,
            'gas_price_bsc': bridge_info.gas_price_bsc,
            'bridge_fee_rate': bridge_info.bridge_fee_rate,
            'eth_block': bridge_info.eth_block_number,
            'bsc_block': bridge_info.bsc_block_number,
        }


def create_binance_bridge(
    api_key: str = "",
    api_secret: str = "",
    private_key: Optional[str] = None,
    **kwargs
) -> BinanceBridge:
    """
    Factory pour créer un bridge Binance.

    Args:
        api_key: Clé API Binance
        api_secret: Secret API Binance
        private_key: Clé privée Ethereum
        **kwargs: Arguments supplémentaires

    Returns:
        BinanceBridge: Instance du bridge
    """
    config = BinanceBridgeConfig(
        api_key=api_key,
        api_secret=api_secret,
        private_key=private_key,
        **kwargs
    )
    return BinanceBridge(config)


__all__ = [
    'BinanceBridge',
    'BinanceBridgeConfig',
    'BinanceTransaction',
    'BinanceBridgeInfo',
    'create_binance_bridge',
]

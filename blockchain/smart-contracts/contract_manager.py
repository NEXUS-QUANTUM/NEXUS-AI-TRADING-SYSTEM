# blockchain/smart-contracts/contract_manager.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Contract Manager - Gestion des Contrats Intelligents

Ce module implémente un système complet de gestion des contrats intelligents,
supportant le déploiement, l'interaction, le monitoring, et l'audit des
contrats sur multiples blockchains.

Fonctionnalités principales:
- Déploiement de contrats
- Interaction avec les contrats
- Monitoring des événements
- Gestion des versions
- Audit de sécurité
- Support multi-chaînes
- Gestion des ABIs
- Gestion des upgrades
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from functools import lru_cache, wraps
from pathlib import Path

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, ContractError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..nodes.base_node import BaseNode
    from ..nodes.node_manager import NodeManager
    from ..nodes.node_rpc import NodeRPCClient, RPCMethod
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, ContractError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..nodes.base_node import BaseNode
    from ..nodes.node_manager import NodeManager
    from ..nodes.node_rpc import NodeRPCClient, RPCMethod
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ContractStatus(Enum):
    """Statuts des contrats"""
    DEPLOYED = "deployed"
    VERIFIED = "verified"
    AUDITED = "audited"
    UPGRADED = "upgraded"
    DEPRECATED = "deprecated"
    PAUSED = "paused"
    DESTROYED = "destroyed"


class ContractType(Enum):
    """Types de contrats"""
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    DEFI = "defi"
    BRIDGE = "bridge"
    STAKING = "staking"
    GOVERNANCE = "governance"
    PROXY = "proxy"
    FACTORY = "factory"
    CUSTOM = "custom"


@dataclass
class ContractInfo:
    """Informations d'un contrat"""
    address: str
    chain: str
    name: str
    contract_type: ContractType
    version: str
    abi: List[Dict[str, Any]]
    bytecode: Optional[str] = None
    deployed_block: Optional[int] = None
    deployer: Optional[str] = None
    status: ContractStatus = ContractStatus.DEPLOYED
    verified: bool = False
    audits: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "chain": self.chain,
            "name": self.name,
            "contract_type": self.contract_type.value,
            "version": self.version,
            "abi": self.abi,
            "bytecode": self.bytecode[:100] + "..." if self.bytecode else None,
            "deployed_block": self.deployed_block,
            "deployer": self.deployer,
            "status": self.status.value,
            "verified": self.verified,
            "audits": self.audits,
            "events": self.events,
            "metadata": self.metadata,
        }


@dataclass
class ContractDeployment:
    """Déploiement de contrat"""
    deployment_id: str
    chain: str
    contract_type: ContractType
    name: str
    version: str
    address: Optional[str] = None
    tx_hash: Optional[str] = None
    deployer: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "deployment_id": self.deployment_id,
            "chain": self.chain,
            "contract_type": self.contract_type.value,
            "name": self.name,
            "version": self.version,
            "address": self.address,
            "tx_hash": self.tx_hash,
            "deployer": self.deployer,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class ContractCall:
    """Appel de contrat"""
    call_id: str
    contract_address: str
    chain: str
    function: str
    args: List[Any]
    kwargs: Dict[str, Any]
    caller: str
    tx_hash: Optional[str] = None
    result: Optional[Any] = None
    status: str = "pending"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "call_id": self.call_id,
            "contract_address": self.contract_address,
            "chain": self.chain,
            "function": self.function,
            "args": self.args,
            "kwargs": self.kwargs,
            "caller": self.caller,
            "tx_hash": self.tx_hash,
            "result": str(self.result) if self.result else None,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# ABIS DES CONTRATS STANDARDS
# ============================================================

STANDARD_ABIS = {
    "erc20": [
        {
            "constant": True,
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "spender", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "recipient", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "name",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ],
    "erc721": [
        {
            "constant": True,
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "tokenId", "type": "uint256"}],
            "name": "ownerOf",
            "outputs": [{"name": "", "type": "address"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
            ],
            "name": "safeTransferFrom",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "tokenId", "type": "uint256"}],
            "name": "tokenURI",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ],
    "erc1155": [
        {
            "constant": True,
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "id", "type": "uint256"},
            ],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "id", "type": "uint256"},
                {"name": "amount", "type": "uint256"},
                {"name": "data", "type": "bytes"},
            ],
            "name": "safeTransferFrom",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "id", "type": "uint256"}],
            "name": "uri",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ],
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class ContractManager:
    """
    Gestionnaire avancé des contrats intelligents
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        node_manager: NodeManager,
        rpc_client: NodeRPCClient,
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de contrats

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.node_manager = node_manager
        self.rpc_client = rpc_client
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, ContractInfo] = {}
        self._deployments: Dict[str, ContractDeployment] = {}
        self._calls: List[ContractCall] = []
        self._events: List[Dict[str, Any]] = []
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des ABIs
        self._abi_cache: Dict[str, List[Dict[str, Any]]] = {}

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Initialisation
        self._load_abis()

        logger.info("ContractManager initialisé avec succès")

    def _load_abis(self) -> None:
        """Charge les ABIs des contrats standards"""
        for contract_type, abi in STANDARD_ABIS.items():
            self._abi_cache[contract_type] = abi

        logger.info(f"ABIs chargées: {list(self._abi_cache.keys())}")

    # ============================================================
    # MÉTHODES DE DÉPLOIEMENT
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def deploy_contract(
        self,
        deployment: ContractDeployment,
        wallet_address: str,
        bytecode: str,
        constructor_args: List[Any] = None,
    ) -> ContractDeployment:
        """
        Déploie un contrat

        Args:
            deployment: Configuration du déploiement
            wallet_address: Adresse du wallet
            bytecode: Bytecode du contrat
            constructor_args: Arguments du constructeur

        Returns:
            Résultat du déploiement
        """
        logger.info(f"Déploiement du contrat {deployment.name} sur {deployment.chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise ContractError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du provider
            provider = await self._get_provider(deployment.chain)
            if not provider:
                raise ContractError(f"Provider non trouvé pour {deployment.chain}")

            # Construction du contrat
            abi = await self._get_abi(deployment.contract_type, deployment.name)

            # Création du contrat
            contract = provider.eth.contract(
                bytecode=bytecode,
                abi=abi,
            )

            # Construction de la transaction
            deploy_tx = contract.constructor(*constructor_args or []).build_transaction({
                "from": to_checksum_address(wallet_address),
                "nonce": await provider.eth.get_transaction_count(wallet_address),
                "gas": 3000000,
                "gasPrice": await self._get_gas_price(deployment.chain),
            })

            # Signature et envoi
            signed_tx = wallet.sign_transaction(deploy_tx)
            tx_hash = await self._send_transaction(deployment.chain, signed_tx)

            # Attente du déploiement
            receipt = await self._wait_for_transaction(deployment.chain, tx_hash)

            # Récupération de l'adresse
            contract_address = receipt.get("contractAddress", "")

            if not contract_address:
                raise ContractError("Échec du déploiement: pas d'adresse de contrat")

            # Mise à jour du déploiement
            deployment.address = contract_address
            deployment.tx_hash = tx_hash.hex()
            deployment.deployer = wallet_address
            deployment.status = "completed"
            deployment.completed_at = datetime.now()

            # Enregistrement du contrat
            contract_info = ContractInfo(
                address=contract_address,
                chain=deployment.chain,
                name=deployment.name,
                contract_type=deployment.contract_type,
                version=deployment.version,
                abi=abi,
                bytecode=bytecode,
                deployed_block=receipt.get("blockNumber"),
                deployer=wallet_address,
                status=ContractStatus.DEPLOYED,
                metadata=deployment.metadata,
            )

            self._contracts[contract_address] = contract_info
            self._deployments[deployment.deployment_id] = deployment

            self.metrics.record_increment(
                "contract_deployed",
                1,
                {
                    "chain": deployment.chain,
                    "type": deployment.contract_type.value,
                    "name": deployment.name,
                },
            )

            logger.info(f"Contrat {contract_address} déployé avec succès")
            return deployment

        except Exception as e:
            logger.error(f"Erreur de déploiement: {e}")
            deployment.status = "failed"
            deployment.error_message = str(e)
            self._deployments[deployment.deployment_id] = deployment
            raise ContractError(f"Erreur de déploiement: {e}")

    # ============================================================
    # MÉTHODES D'INTERACTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def call_contract(
        self,
        contract_address: str,
        function_name: str,
        args: List[Any],
        wallet_address: str,
        chain: str,
        value: Optional[Decimal] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> ContractCall:
        """
        Appelle une fonction d'un contrat

        Args:
            contract_address: Adresse du contrat
            function_name: Nom de la fonction
            args: Arguments
            wallet_address: Adresse du wallet
            chain: Chaîne
            value: Valeur en ETH (optionnel)
            kwargs: Arguments nommés

        Returns:
            Résultat de l'appel
        """
        call_id = f"call_{uuid.uuid4().hex[:12]}"
        logger.info(f"Appel du contrat {contract_address} - {function_name}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise ContractError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du contrat
            contract = await self._get_contract(contract_address, chain)

            # Construction de l'appel
            contract_function = getattr(contract.functions, function_name)

            # Appel de la fonction
            if value:
                tx = contract_function(*args, **kwargs or {}).build_transaction({
                    "from": to_checksum_address(wallet_address),
                    "value": int(value * Decimal(1e18)),
                    "gas": 300000,
                    "gasPrice": await self._get_gas_price(chain),
                })
            else:
                tx = contract_function(*args, **kwargs or {}).build_transaction({
                    "from": to_checksum_address(wallet_address),
                    "gas": 300000,
                    "gasPrice": await self._get_gas_price(chain),
                })

            # Envoi de la transaction
            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(chain, tx_hash)

            # Récupération du résultat
            result = None
            if receipt.get("status") == 1:
                # Récupération des logs
                events = await self._parse_events(contract, receipt)
                result = events

            call = ContractCall(
                call_id=call_id,
                contract_address=contract_address,
                chain=chain,
                function=function_name,
                args=args,
                kwargs=kwargs or {},
                caller=wallet_address,
                tx_hash=tx_hash.hex(),
                result=result,
                status="completed" if receipt.get("status") == 1 else "failed",
                metadata={"receipt": dict(receipt)},
            )

            self._calls.append(call)

            self.metrics.record_increment(
                "contract_call",
                1,
                {
                    "chain": chain,
                    "function": function_name,
                    "status": call.status,
                },
            )

            return call

        except Exception as e:
            logger.error(f"Erreur d'appel: {e}")
            call = ContractCall(
                call_id=call_id,
                contract_address=contract_address,
                chain=chain,
                function=function_name,
                args=args,
                kwargs=kwargs or {},
                caller=wallet_address,
                status="failed",
                metadata={"error": str(e)},
            )
            self._calls.append(call)
            raise ContractError(f"Erreur d'appel: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def view_contract(
        self,
        contract_address: str,
        function_name: str,
        args: List[Any],
        chain: str,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Appelle une fonction de vue d'un contrat

        Args:
            contract_address: Adresse du contrat
            function_name: Nom de la fonction
            args: Arguments
            chain: Chaîne
            kwargs: Arguments nommés

        Returns:
            Résultat de l'appel
        """
        try:
            contract = await self._get_contract(contract_address, chain)

            # Appel de la fonction
            contract_function = getattr(contract.functions, function_name)
            result = contract_function(*args, **kwargs or {}).call()

            return result

        except Exception as e:
            logger.error(f"Erreur de vue: {e}")
            raise ContractError(f"Erreur de vue: {e}")

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_contract(self, address: str, chain: str) -> Optional[ContractInfo]:
        """
        Obtient les informations d'un contrat

        Args:
            address: Adresse du contrat
            chain: Chaîne

        Returns:
            Informations du contrat
        """
        return self._contracts.get(address)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_contract_by_name(self, name: str, chain: str) -> Optional[ContractInfo]:
        """
        Obtient un contrat par son nom

        Args:
            name: Nom du contrat
            chain: Chaîne

        Returns:
            Informations du contrat
        """
        for contract in self._contracts.values():
            if contract.name == name and contract.chain == chain:
                return contract
        return None

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_deployment(self, deployment_id: str) -> Optional[ContractDeployment]:
        """
        Obtient un déploiement

        Args:
            deployment_id: ID du déploiement

        Returns:
            Déploiement
        """
        return self._deployments.get(deployment_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_calls(
        self,
        contract_address: Optional[str] = None,
        limit: int = 100,
    ) -> List[ContractCall]:
        """
        Obtient les appels de contrats

        Args:
            contract_address: Adresse du contrat (optionnel)
            limit: Nombre maximum

        Returns:
            Liste des appels
        """
        calls = self._calls

        if contract_address:
            calls = [c for c in calls if c.contract_address == contract_address]

        return calls[-limit:]

    # ============================================================
    # MÉTHODES D'AUDIT
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def audit_contract(
        self,
        contract_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Audite un contrat

        Args:
            contract_address: Adresse du contrat
            chain: Chaîne

        Returns:
            Résultat de l'audit
        """
        logger.info(f"Audit du contrat {contract_address}")

        try:
            contract = await self._get_contract(contract_address, chain)

            # Analyse de sécurité
            security_issues = await self._analyze_security(contract)

            # Vérification des permissions
            permissions = await self._check_permissions(contract)

            # Analyse des événements
            events = await self._analyze_events(contract)

            audit_result = {
                "address": contract_address,
                "chain": chain,
                "security_issues": security_issues,
                "permissions": permissions,
                "events": events,
                "score": self._calculate_audit_score(security_issues),
                "timestamp": datetime.now().isoformat(),
            }

            # Mise à jour du contrat
            if contract_address in self._contracts:
                self._contracts[contract_address].audits.append(audit_result)

            return audit_result

        except Exception as e:
            logger.error(f"Erreur d'audit: {e}")
            raise ContractError(f"Erreur d'audit: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_provider(self, chain: str) -> Optional[Web3]:
        """Obtient le provider Web3"""
        try:
            protocol = self._get_protocol_from_chain(chain)
            nodes = await self.node_manager.get_nodes_by_protocol(protocol)
            if nodes and nodes[0]:
                return nodes[0].web3_provider
            return None
        except Exception:
            return None

    async def _get_contract(self, address: str, chain: str) -> Contract:
        """Obtient un contrat"""
        provider = await self._get_provider(chain)
        if not provider:
            raise ContractError(f"Provider non trouvé pour {chain}")

        # Récupération de l'ABI
        contract_info = self._contracts.get(address)
        if not contract_info:
            raise ContractError(f"Contrat {address} non trouvé")

        return provider.eth.contract(
            address=to_checksum_address(address),
            abi=contract_info.abi,
        )

    async def _get_abi(self, contract_type: ContractType, name: str) -> List[Dict[str, Any]]:
        """Obtient l'ABI d'un contrat"""
        # Vérification du cache
        cache_key = f"{contract_type.value}:{name}"
        if cache_key in self._abi_cache:
            return self._abi_cache[cache_key]

        # Recherche dans les fichiers
        abi_path = Path(__file__).parent / "abis" / f"{name}.json"
        if abi_path.exists():
            with open(abi_path, 'r') as f:
                abi = json.load(f)
                self._abi_cache[cache_key] = abi
                return abi

        # Fallback: ABI standard
        if contract_type.value in STANDARD_ABIS:
            return STANDARD_ABIS[contract_type.value]

        raise ContractError(f"ABI non trouvée pour {name}")

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            result = await self.rpc_client.call(
                method=RPCMethod.ETH_GET_GAS_PRICE,
                params=[],
                endpoint=await self._get_endpoint(chain),
            )
            if result.is_success():
                return int(result.result, 16)
            return 50000000000  # 50 Gwei par défaut
        except Exception:
            return 50000000000

    async def _get_endpoint(self, chain: str) -> str:
        """Obtient l'endpoint RPC"""
        nodes = await self.node_manager.get_nodes_by_protocol(
            self._get_protocol_from_chain(chain)
        )
        if nodes and nodes[0]:
            return nodes[0].config.endpoint
        return ""

    def _get_protocol_from_chain(self, chain: str) -> str:
        """Convertit le nom de la chaîne en protocole"""
        chain_map = {
            "ethereum": "ethereum",
            "bsc": "bsc",
            "polygon": "polygon",
            "arbitrum": "arbitrum",
            "optimism": "optimism",
            "avalanche": "avalanche",
            "solana": "solana",
            "base": "base",
        }
        return chain_map.get(chain, "ethereum")

    async def _send_transaction(self, chain: str, signed_tx: Any) -> HexBytes:
        """Envoie une transaction"""
        provider = await self._get_provider(chain)
        if not provider:
            raise ContractError(f"Provider non trouvé pour {chain}")

        return await provider.eth.send_raw_transaction(signed_tx)

    async def _wait_for_transaction(self, chain: str, tx_hash: HexBytes) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        provider = await self._get_provider(chain)
        if not provider:
            raise ContractError(f"Provider non trouvé pour {chain}")

        start_time = time.time()
        while time.time() - start_time < 300:
            receipt = await provider.eth.get_transaction_receipt(tx_hash)
            if receipt:
                return dict(receipt)
            await asyncio.sleep(2)

        raise ContractError(f"Timeout de transaction: {tx_hash.hex()}")

    async def _parse_events(self, contract: Contract, receipt: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse les événements d'un contrat"""
        events = []
        for log in receipt.get("logs", []):
            try:
                event = contract.events.process_log(log)
                if event:
                    events.append(event)
            except Exception:
                continue
        return events

    async def _analyze_security(self, contract: Contract) -> List[Dict[str, Any]]:
        """Analyse la sécurité d'un contrat"""
        issues = []

        # Vérifications de base
        # Dans la réalité, on utiliserait des outils d'analyse statique

        return issues

    async def _check_permissions(self, contract: Contract) -> Dict[str, Any]:
        """Vérifie les permissions d'un contrat"""
        return {"owner": "0x...", "permissions": []}

    async def _analyze_events(self, contract: Contract) -> List[Dict[str, Any]]:
        """Analyse les événements d'un contrat"""
        return []

    def _calculate_audit_score(self, issues: List[Dict[str, Any]]) -> int:
        """Calcule le score d'audit"""
        # Score de base
        score = 100

        # Pénalités
        for issue in issues:
            if issue.get("severity") == "critical":
                score -= 20
            elif issue.get("severity") == "high":
                score -= 10
            elif issue.get("severity") == "medium":
                score -= 5
            elif issue.get("severity") == "low":
                score -= 2

        return max(0, score)

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        total_contracts = len(self._contracts)
        total_deployments = len(self._deployments)
        total_calls = len(self._calls)

        return {
            "total_contracts": total_contracts,
            "total_deployments": total_deployments,
            "total_calls": total_calls,
            "contracts_by_type": self._get_contracts_by_type(),
            "deployments_by_status": self._get_deployments_by_status(),
            "success_rate": self._calculate_success_rate(),
            "cache_size": len(self._abi_cache),
        }

    def _get_contracts_by_type(self) -> Dict[str, int]:
        """Obtient le nombre de contrats par type"""
        counts = defaultdict(int)
        for contract in self._contracts.values():
            counts[contract.contract_type.value] += 1
        return dict(counts)

    def _get_deployments_by_status(self) -> Dict[str, int]:
        """Obtient le nombre de déploiements par statut"""
        counts = defaultdict(int)
        for deployment in self._deployments.values():
            counts[deployment.status] += 1
        return dict(counts)

    def _calculate_success_rate(self) -> float:
        """Calcule le taux de succès"""
        total = len(self._deployments)
        if total == 0:
            return 0.0

        successful = len([d for d in self._deployments.values() if d.status == "completed"])
        return successful / total

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources ContractManager...")

        self._contracts.clear()
        self._deployments.clear()
        self._calls.clear()
        self._events.clear()
        self._abi_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_contract_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    node_manager: NodeManager,
    rpc_client: NodeRPCClient,
    **kwargs,
) -> ContractManager:
    """
    Crée une instance de ContractManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        node_manager: Gestionnaire de nœuds
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de ContractManager
    """
    return ContractManager(
        config=config,
        wallet_manager=wallet_manager,
        node_manager=node_manager,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de ContractManager"""
    # Configuration
    config = {}

    # Création des dépendances (simplifiées)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    class SimpleNodeManager:
        async def get_nodes_by_protocol(self, protocol):
            return []

    class SimpleRPCClient:
        async def call(self, method, params, endpoint):
            return type('Response', (), {'is_success': lambda: True, 'result': '0x0'})

    wallet_manager = SimpleWalletManager()
    node_manager = SimpleNodeManager()
    rpc_client = SimpleRPCClient()

    # Création du gestionnaire
    manager = create_contract_manager(
        config=config,
        wallet_manager=wallet_manager,
        node_manager=node_manager,
        rpc_client=rpc_client,
    )

    # Déploiement d'un contrat
    deployment = ContractDeployment(
        deployment_id=f"dep_{uuid.uuid4().hex[:12]}",
        chain="ethereum",
        contract_type=ContractType.ERC20,
        name="MyToken",
        version="1.0.0",
        metadata={"symbol": "MTK", "decimals": 18},
    )

    result = await manager.deploy_contract(
        deployment=deployment,
        wallet_address="0x1234567890123456789012345678901234567890",
        bytecode="0x...",
        constructor_args=["MyToken", "MTK", 18, 1000000000000000000000000],
    )

    print(f"Déploiement: {result.to_dict()}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

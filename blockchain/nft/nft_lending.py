# blockchain/nft/nft_lending.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Lending - Gestion des Prêts NFT

Ce module implémente un système complet de prêts NFT, permettant
le lending, l'emprunt, la gestion des collatéraux, et l'optimisation
des stratégies de prêt.

Fonctionnalités principales:
- Prêt de NFTs (lending)
- Emprunt de NFTs (borrowing)
- Gestion des collatéraux
- Calcul des taux d'intérêt
- Gestion des liquidations
- Monitoring des prêts
- Alertes de liquidation
- Support multi-protocoles
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
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTStandard, NFTStatus
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTStandard, NFTStatus

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NFTLendingProtocol(Enum):
    """Protocoles de prêt NFT supportés"""
    BLUR = "blur"
    NFTFI = "nftfi"
    BENDDAO = "benddao"
    PARA_SPACE = "para_space"
    ARCADE = "arcade"
    GOPROTOCOL = "goprotocol"


class NFTLoanStatus(Enum):
    """Statuts d'un prêt NFT"""
    ACTIVE = "active"
    PENDING = "pending"
    REPAID = "repaid"
    LIQUIDATED = "liquidated"
    DEFAULTED = "defaulted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class NFTLoanType(Enum):
    """Types de prêt NFT"""
    COLLATERAL = "collateral"  # NFT comme collatéral
    CASH = "cash"  # Prêt cash contre NFT
    RENTAL = "rental"  # Location de NFT


@dataclass
class NFTLoan:
    """Prêt NFT"""
    loan_id: str
    protocol: NFTLendingProtocol
    chain: str
    contract_address: str
    token_id: str
    lender: str
    borrower: str
    amount: Decimal
    currency: str
    interest_rate: Decimal
    duration: int  # secondes
    start_time: datetime
    end_time: datetime
    status: NFTLoanStatus
    collateral_value: Decimal
    liquidation_threshold: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "loan_id": self.loan_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "lender": self.lender,
            "borrower": self.borrower,
            "amount": str(self.amount),
            "currency": self.currency,
            "interest_rate": str(self.interest_rate),
            "duration": self.duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status.value,
            "collateral_value": str(self.collateral_value),
            "liquidation_threshold": str(self.liquidation_threshold),
            "metadata": self.metadata,
        }


@dataclass
class NFTLendingQuote:
    """Devis de prêt NFT"""
    quote_id: str
    protocol: NFTLendingProtocol
    chain: str
    contract_address: str
    token_id: str
    amount: Decimal
    currency: str
    interest_rate: Decimal
    duration: int
    loan_to_value: Decimal
    estimated_fees: Decimal
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "amount": str(self.amount),
            "currency": self.currency,
            "interest_rate": str(self.interest_rate),
            "duration": self.duration,
            "loan_to_value": str(self.loan_to_value),
            "estimated_fees": str(self.estimated_fees),
            "confidence": self.confidence,
        }


@dataclass
class NFTLendingPosition:
    """Position de prêt NFT"""
    position_id: str
    loan_id: str
    user: str
    role: str  # "lender" or "borrower"
    total_value: Decimal
    active_loans: int
    total_interest_earned: Decimal
    total_interest_paid: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "loan_id": self.loan_id,
            "user": self.user,
            "role": self.role,
            "total_value": str(self.total_value),
            "active_loans": self.active_loans,
            "total_interest_earned": str(self.total_interest_earned),
            "total_interest_paid": str(self.total_interest_paid),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# ADRESSES DES PROTOCOLES
# ============================================================

LENDING_PROTOCOL_ADDRESSES = {
    NFTLendingProtocol.BLUR: {
        "ethereum": {
            "lending": "0x29469395eAf6f95920E59F858042f0e28D98a20B",
        },
    },
    NFTLendingProtocol.BENDDAO: {
        "ethereum": {
            "lending": "0x...",
        },
    },
    NFTLendingProtocol.NFTFI: {
        "ethereum": {
            "lending": "0x...",
        },
    },
}


# ============================================================
# ABIS DES CONTRATS
# ============================================================

NFT_LENDING_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "nft", "type": "address"},
            {"name": "id", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
            {"name": "duration", "type": "uint256"},
            {"name": "interestRate", "type": "uint256"},
        ],
        "name": "offerLoan",
        "outputs": [{"name": "loanId", "type": "bytes32"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "loanId", "type": "bytes32"},
        ],
        "name": "acceptLoan",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "loanId", "type": "bytes32"},
        ],
        "name": "repayLoan",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "loanId", "type": "bytes32"},
        ],
        "name": "liquidateLoan",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "loanId", "type": "bytes32"}],
        "name": "getLoanInfo",
        "outputs": [
            {"name": "nft", "type": "address"},
            {"name": "id", "type": "uint256"},
            {"name": "lender", "type": "address"},
            {"name": "borrower", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRate", "type": "uint256"},
            {"name": "startTime", "type": "uint256"},
            {"name": "endTime", "type": "uint256"},
            {"name": "status", "type": "uint8"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTLendingManager(BaseNFT):
    """
    Gestionnaire de prêts NFT
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Web3],
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de prêts NFT

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, Dict[str, Dict[str, Contract]]] = {}
        self._loans_cache: Dict[str, Tuple[float, NFTLoan]] = {}
        self._positions_cache: Dict[str, Tuple[float, NFTLendingPosition]] = {}
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

        # Cache des prix
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}

        # Métriques
        self._total_loans = 0
        self._total_volume = Decimal("0")
        self._total_interest = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        # Chargement des prêts existants
        self._load_loans()

        logger.info("NFTLendingManager initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats de prêt NFT"""
        try:
            self._contracts = {}

            for protocol, chain_config in LENDING_PROTOCOL_ADDRESSES.items():
                for chain, addresses in chain_config.items():
                    if chain not in self.web3_providers:
                        continue

                    provider = self.web3_providers[chain]
                    self._contracts[protocol.value] = self._contracts.get(protocol.value, {})
                    self._contracts[protocol.value][chain] = {}

                    for name, address in addresses.items():
                        self._contracts[protocol.value][chain][name] = provider.eth.contract(
                            address=to_checksum_address(address),
                            abi=NFT_LENDING_ABI,
                        )

            logger.info(f"Contrats de prêt NFT chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise NFTError(f"Erreur de chargement des contrats: {e}")

    def _load_loans(self) -> None:
        """Charge les prêts existants"""
        # Dans une implémentation réelle, on chargerait depuis une base de données
        pass

    # ============================================================
    # MÉTHODES PUBLIQUES - OFFRES DE PRÊT
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def offer_loan(
        self,
        protocol: NFTLendingProtocol,
        contract_address: str,
        token_id: str,
        amount: Decimal,
        wallet_address: str,
        currency: str = "ETH",
        interest_rate: Decimal = Decimal("0.1"),
        duration: int = 86400,  # 1 jour
    ) -> NFTLoan:
        """
        Offre un prêt sur un NFT

        Args:
            protocol: Protocole de prêt
            contract_address: Adresse du contrat NFT
            token_id: ID du token
            amount: Montant du prêt
            wallet_address: Adresse du wallet
            currency: Devise
            interest_rate: Taux d'intérêt
            duration: Durée en secondes

        Returns:
            Prêt créé
        """
        logger.info(f"Offre de prêt sur {contract_address}/{token_id} pour {amount} {currency}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Récupération de la valeur du collatéral
            collateral_value = await self._get_nft_value(contract_address, token_id)

            # Vérification du LTV
            ltv = amount / collateral_value
            if ltv > Decimal("0.7"):
                raise NFTError(f"LTV {ltv:.2%} trop élevé")

            # Récupération du contrat de prêt
            loan_contract = self._get_loan_contract(protocol, "ethereum")
            if not loan_contract:
                raise NFTError(f"Contrat de prêt non trouvé pour {protocol.value}")

            # Approval du NFT
            await self._approve_nft(
                contract_address=contract_address,
                token_id=token_id,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=loan_contract.address,
            )

            amount_wei = int(amount * Decimal(1e18))
            rate_wei = int(interest_rate * Decimal(1e18))

            tx = loan_contract.functions.offerLoan(
                to_checksum_address(contract_address),
                int(token_id),
                amount_wei,
                duration,
                rate_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            loan_id = f"loan_{uuid.uuid4().hex[:12]}"
            loan = NFTLoan(
                loan_id=loan_id,
                protocol=protocol,
                chain="ethereum",
                contract_address=contract_address,
                token_id=token_id,
                lender=wallet_address,
                borrower="",
                amount=amount,
                currency=currency,
                interest_rate=interest_rate,
                duration=duration,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(seconds=duration),
                status=NFTLoanStatus.PENDING,
                collateral_value=collateral_value,
                liquidation_threshold=Decimal("0.8"),
                metadata={"tx_hash": tx_hash.hex()},
            )

            self._loans_cache[loan_id] = (time.time(), loan)
            self._total_loans += 1

            self.metrics.record_increment(
                "nft_loan_offered",
                1,
                {"protocol": protocol.value, "currency": currency},
            )

            logger.info(f"Offre de prêt créée: {loan_id}")
            return loan

        except Exception as e:
            logger.error(f"Erreur d'offre de prêt: {e}")
            raise NFTError(f"Erreur d'offre de prêt: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def accept_loan(
        self,
        loan_id: str,
        wallet_address: str,
    ) -> str:
        """
        Accepte un prêt offert

        Args:
            loan_id: ID du prêt
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Acceptation du prêt {loan_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            loan = await self.get_loan(loan_id)
            if not loan:
                raise NFTError(f"Prêt {loan_id} non trouvé")

            if loan.status != NFTLoanStatus.PENDING:
                raise NFTError(f"Le prêt {loan_id} n'est pas en attente")

            # Vérification du solde
            balance = await self._get_balance(loan.currency, wallet_address)
            if balance < loan.amount:
                raise NFTError(f"Solde insuffisant: {balance} < {loan.amount}")

            loan_contract = self._get_loan_contract(loan.protocol, loan.chain)
            if not loan_contract:
                raise NFTError(f"Contrat de prêt non trouvé")

            tx = loan_contract.functions.acceptLoan(
                loan_id,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            loan.status = NFTLoanStatus.ACTIVE
            loan.borrower = wallet_address
            loan.start_time = datetime.now()
            loan.end_time = datetime.now() + timedelta(seconds=loan.duration)

            self.metrics.record_increment(
                "nft_loan_accepted",
                1,
                {"protocol": loan.protocol.value},
            )

            logger.info(f"Prêt accepté: {loan_id}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur d'acceptation de prêt: {e}")
            raise NFTError(f"Erreur d'acceptation de prêt: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - REMBOURSEMENT
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def repay_loan(
        self,
        loan_id: str,
        wallet_address: str,
    ) -> str:
        """
        Rembourse un prêt

        Args:
            loan_id: ID du prêt
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Remboursement du prêt {loan_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            loan = await self.get_loan(loan_id)
            if not loan:
                raise NFTError(f"Prêt {loan_id} non trouvé")

            if loan.status != NFTLoanStatus.ACTIVE:
                raise NFTError(f"Le prêt {loan_id} n'est pas actif")

            # Calcul du montant total avec intérêts
            total_amount = loan.amount * (Decimal("1") + loan.interest_rate)

            # Vérification du solde
            balance = await self._get_balance(loan.currency, wallet_address)
            if balance < total_amount:
                raise NFTError(f"Solde insuffisant: {balance} < {total_amount}")

            loan_contract = self._get_loan_contract(loan.protocol, loan.chain)
            if not loan_contract:
                raise NFTError(f"Contrat de prêt non trouvé")

            tx = loan_contract.functions.repayLoan(
                loan_id,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            loan.status = NFTLoanStatus.REPAID

            self._total_interest += loan.amount * loan.interest_rate
            self.metrics.record_increment(
                "nft_loan_repaid",
                1,
                {"protocol": loan.protocol.value},
            )

            logger.info(f"Prêt remboursé: {loan_id}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de remboursement: {e}")
            raise NFTError(f"Erreur de remboursement: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def liquidate_loan(
        self,
        loan_id: str,
        wallet_address: str,
    ) -> str:
        """
        Liquide un prêt

        Args:
            loan_id: ID du prêt
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Liquidation du prêt {loan_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            loan = await self.get_loan(loan_id)
            if not loan:
                raise NFTError(f"Prêt {loan_id} non trouvé")

            if loan.status != NFTLoanStatus.ACTIVE:
                raise NFTError(f"Le prêt {loan_id} n'est pas actif")

            # Vérification de la condition de liquidation
            current_value = await self._get_nft_value(
                loan.contract_address, loan.token_id
            )

            if current_value / loan.amount > Decimal("1.1"):
                raise NFTError("Le prêt ne peut pas être liquidé")

            loan_contract = self._get_loan_contract(loan.protocol, loan.chain)
            if not loan_contract:
                raise NFTError(f"Contrat de prêt non trouvé")

            tx = loan_contract.functions.liquidateLoan(
                loan_id,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            loan.status = NFTLoanStatus.LIQUIDATED

            self.metrics.record_increment(
                "nft_loan_liquidated",
                1,
                {"protocol": loan.protocol.value},
            )

            logger.info(f"Prêt liquidé: {loan_id}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de liquidation: {e}")
            raise NFTError(f"Erreur de liquidation: {e}")

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_loan(self, loan_id: str) -> Optional[NFTLoan]:
        """
        Obtient les données d'un prêt

        Args:
            loan_id: ID du prêt

        Returns:
            Prêt ou None
        """
        if loan_id in self._loans_cache:
            cached_time, loan = self._loans_cache[loan_id]
            if time.time() - cached_time < self.cache_ttl:
                return loan

        # Dans la réalité, on interrogerait les contrats
        # Simulé pour l'exemple
        return None

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_loans_by_lender(self, lender: str) -> List[NFTLoan]:
        """
        Obtient les prêts d'un prêteur

        Args:
            lender: Adresse du prêteur

        Returns:
            Liste des prêts
        """
        loans = []
        for _, (_, loan) in self._loans_cache.items():
            if loan.lender.lower() == lender.lower():
                loans.append(loan)
        return loans

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_loans_by_borrower(self, borrower: str) -> List[NFTLoan]:
        """
        Obtient les prêts d'un emprunteur

        Args:
            borrower: Adresse de l'emprunteur

        Returns:
            Liste des prêts
        """
        loans = []
        for _, (_, loan) in self._loans_cache.items():
            if loan.borrower.lower() == borrower.lower():
                loans.append(loan)
        return loans

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_loans(
        self,
        interval: int = 300,
    ) -> None:
        """
        Surveille les prêts en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des prêts NFT")

        while True:
            try:
                for loan_id, (_, loan) in list(self._loans_cache.items()):
                    if loan.status != NFTLoanStatus.ACTIVE:
                        continue

                    # Vérification du temps restant
                    if loan.end_time < datetime.now():
                        # Prêt expiré
                        loan.status = NFTLoanStatus.EXPIRED
                        await self._send_alert({
                            "type": "loan_expired",
                            "loan_id": loan_id,
                            "severity": "warning",
                        })

                    # Vérification du collatéral
                    current_value = await self._get_nft_value(
                        loan.contract_address, loan.token_id
                    )

                    if current_value / loan.amount < loan.liquidation_threshold:
                        await self._send_alert({
                            "type": "loan_liquidation_warning",
                            "loan_id": loan_id,
                            "current_value": str(current_value),
                            "threshold": str(loan.liquidation_threshold),
                            "severity": "critical",
                        })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_loan_contract(
        self,
        protocol: NFTLendingProtocol,
        chain: str,
    ) -> Optional[Contract]:
        """Obtient le contrat de prêt"""
        protocol_contracts = self._contracts.get(protocol.value, {})
        chain_contracts = protocol_contracts.get(chain, {})
        return chain_contracts.get("lending")

    async def _approve_nft(
        self,
        contract_address: str,
        token_id: str,
        wallet_address: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un NFT pour un contrat"""
        try:
            provider = self.web3_providers["ethereum"]
            contract = provider.eth.contract(
                address=to_checksum_address(contract_address),
                abi=self.ERC721_ABI,
            )

            approved = await contract.functions.getApproved(
                int(token_id)
            ).call()

            if approved.lower() == spender.lower():
                return True

            tx = contract.functions.approve(
                to_checksum_address(spender),
                int(token_id),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            await self._send_transaction("ethereum", signed_tx)

            logger.info(f"Approval NFT réussi")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval NFT: {e}")
            raise NFTError(f"Erreur d'approval NFT: {e}")

    async def _get_nft_value(self, contract_address: str, token_id: str) -> Decimal:
        """Obtient la valeur d'un NFT"""
        # Dans la réalité, on interrogerait les oracles de prix
        # Simulé pour l'exemple
        return Decimal("1")

    async def _get_balance(self, currency: str, address: str) -> Decimal:
        """Obtient le solde d'une adresse"""
        try:
            provider = self.web3_providers["ethereum"]
            if currency.upper() == "ETH":
                balance = await provider.eth.get_balance(
                    to_checksum_address(address)
                )
                return Decimal(str(balance)) / Decimal(1e18)
            return Decimal("0")
        except Exception:
            return Decimal("0")

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 50000000000
            return await provider.eth.gas_price
        except Exception:
            return 50000000000

    async def _send_transaction(self, chain: str, signed_tx: Any) -> HexBytes:
        """Envoie une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise NFTError(f"Provider Web3 non trouvé pour {chain}")

            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise NFTError("Transaction échouée")

            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise NFTError(f"Erreur d'envoi de transaction: {e}")

    async def _wait_for_transaction(
        self,
        provider: Web3,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return dict(receipt)
            except Exception:
                pass
            await asyncio.sleep(2)

        raise NFTError(f"Timeout de transaction: {tx_hash.hex()}")

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        if hasattr(self, "_alert_callbacks"):
            for callback in getattr(self, "_alert_callbacks", []):
                try:
                    await callback(alert)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_loans": self._total_loans,
            "total_volume": str(self._total_volume),
            "total_interest": str(self._total_interest),
            "loans_cached": len(self._loans_cache),
            "positions_cached": len(self._positions_cache),
            "protocols_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTLendingManager...")

        self._loans_cache.clear()
        self._positions_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_lending_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTLendingManager:
    """
    Crée une instance de NFTLendingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTLendingManager
    """
    return NFTLendingManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTLendingManager"""
    # Configuration
    config = {}

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du gestionnaire
    manager = create_nft_lending_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Offre de prêt
    loan = await manager.offer_loan(
        protocol=NFTLendingProtocol.BLUR,
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        amount=Decimal("10"),
        wallet_address="0x1234567890123456789012345678901234567890",
        interest_rate=Decimal("0.1"),
        duration=86400,
    )

    print(f"Offre de prêt: {loan.to_dict()}")

    # Acceptation du prêt (par un autre wallet)
    tx_hash = await manager.accept_loan(
        loan_id=loan.loan_id,
        wallet_address="0x9876543210987654321098765432109876543210",
    )

    print(f"Prêt accepté: {tx_hash}")

    # Remboursement du prêt
    tx_hash = await manager.repay_loan(
        loan_id=loan.loan_id,
        wallet_address="0x9876543210987654321098765432109876543210",
    )

    print(f"Prêt remboursé: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

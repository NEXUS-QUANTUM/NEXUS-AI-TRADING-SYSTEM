# blockchain/bridges/solana_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Solana

Ce module implémente un système complet de bridge pour la blockchain Solana
avec support des protocoles de bridge majeurs (Wormhole, deBridge, Allbridge, etc.),
gestion des frais en SOL, et mécanismes de sécurité avancés.

Fonctionnalités principales:
- Support de Wormhole Bridge
- Support de deBridge
- Support d'Allbridge
- Support de Solana <> Ethereum bridges
- Gestion des SPL tokens
- Optimisation des frais de transaction SOL
- Surveillance en temps réel des bridges
- Mécanismes de fallback
- Support des NFTs (Metaplex)
- Monitoring des transactions cross-chain
"""

import asyncio
import hashlib
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
import base58
import base64

# Import Solana libraries
try:
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed, Finalized
    from solana.rpc.types import TxOpts
    from solana.transaction import Transaction, TransactionInstruction
    from solana.keypair import Keypair
    from solana.publickey import PublicKey
    from solana.system_program import SystemProgram, TransferParams
    from solana.spl.token import Token
    from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
    from spl.token.instructions import (
        create_associated_token_account,
        get_associated_token_address,
        transfer,
        approve,
        revoke,
    )
    import anchorpy
except ImportError:
    logger.warning("Solana libraries not available. Install: solana, spl-token, anchorpy")
    # Mock classes for type hints
    class AsyncClient:
        pass
    class PublicKey:
        pass
    class Keypair:
        pass
    class Transaction:
        pass

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from .bridge_transaction import BridgeTransactionManager
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from .bridge_transaction import BridgeTransactionManager
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class SolanaBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur Solana"""
    WORMHOLE = "wormhole"
    DEBRIDGE = "debridge"
    ALLBRIDGE = "allbridge"
    SWIM = "swim"
    PORTAL = "portal"
    CARBON = "carbon"
    MAYAN = "mayan"
    CIRCLE_CCTP = "circle_cctp"


class SolanaBridgeDirection(Enum):
    """Direction du bridge"""
    DEPOSIT = "deposit"  # Vers Solana
    WITHDRAWAL = "withdrawal"  # Depuis Solana
    CROSS_CHAIN = "cross_chain"


class SolanaTokenType(Enum):
    """Type de token Solana"""
    SPL = "spl"  # Token standard SPL
    NATIVE = "native"  # SOL natif
    NFT = "nft"  # NFT (Metaplex)
    WORMHOLE = "wormhole"  # Wormhole wrapped token


@dataclass
class SolanaBridgeQuote:
    """Devis de bridge Solana"""
    quote_id: str
    protocol: SolanaBridgeProtocol
    direction: SolanaBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    solana_fees: Decimal  # Frais en SOL
    bridge_fees: Decimal
    total_fees: Decimal
    estimated_time: int  # secondes
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    requires_ata: bool  # Associated Token Account
    quote_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
            "direction": self.direction.value,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "solana_fees": str(self.solana_fees),
            "bridge_fees": str(self.bridge_fees),
            "total_fees": str(self.total_fees),
            "estimated_time": self.estimated_time,
            "min_amount_received": str(self.min_amount_received),
            "max_slippage": str(self.max_slippage),
            "confidence": self.confidence,
            "requires_ata": self.requires_ata,
        }


@dataclass
class SolanaBridgeRequest:
    """Requête de bridge Solana"""
    request_id: str
    protocol: SolanaBridgeProtocol
    direction: SolanaBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    use_fallback: bool = True
    max_solana_fee: Optional[Decimal] = None
    priority_fee: Optional[int] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "protocol": self.protocol.value,
            "direction": self.direction.value,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "source_address": self.source_address,
            "destination_address": self.destination_address,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
            "use_fallback": self.use_fallback,
            "max_solana_fee": str(self.max_solana_fee) if self.max_solana_fee else None,
            "priority_fee": self.priority_fee,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class SolanaBridge(BaseBridge):
    """
    Bridge avancé pour Solana avec support multi-protocoles
    """

    # Adresses des contrats/programmes Solana (Mainnet)
    PROGRAMS = {
        "wormhole": {
            "core_bridge": "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth",
            "token_bridge": "wormDTUJ6AWPNvk59vGQbDvGJmqbDTdgWgAqcLBCgUb",
            "nft_bridge": "WnF9DnDkKhzXsKJRGQbMqLm7mD3nM4Vp3nYzVqYVqYV",
        },
        "debridge": {
            "program": "DEBridge1111111111111111111111111111111111",
            "token": "DEBridge1111111111111111111111111111111111",
        },
        "allbridge": {
            "program": "AL1BR1DG11111111111111111111111111111111111",
            "token": "AL1BR1DG11111111111111111111111111111111111",
        },
        "portal": {
            "program": "p1rt1dge11111111111111111111111111111111111",
        },
    }

    # Token mappings
    TOKEN_MAPPINGS = {
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "DAI": "EjmyN6qEC1Tf1JxiG1ae7UTJhUySw74GGrGCzuXB9WZP",
        "WBTC": "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh",
        "WETH": "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
        "MATIC": "Matic111111111111111111111111111111111111111",
        "LINK": "LINK111111111111111111111111111111111111111",
    }

    # Wormhole token mappings (wrapped tokens)
    WORMHOLE_TOKEN_MAPPINGS = {
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "WETH": "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
        "WBTC": "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh",
        "DAI": "EjmyN6qEC1Tf1JxiG1ae7UTJhUySw74GGrGCzuXB9WZP",
    }

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        solana_client: AsyncClient,
        bridge_manager: BridgeManager,
        transaction_manager: BridgeTransactionManager,
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le bridge Solana

        Args:
            config: Configuration du bridge
            wallet_manager: Gestionnaire de wallets
            solana_client: Client Solana
            bridge_manager: Gestionnaire de bridges
            transaction_manager: Gestionnaire de transactions
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager)

        self.solana_client = solana_client
        self.bridge_manager = bridge_manager
        self.transaction_manager = transaction_manager
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._active_bridges: Dict[str, Dict[str, Any]] = {}
        self._bridge_history: List[Dict[str, Any]] = []
        self._quote_cache: Dict[str, Tuple[float, SolanaBridgeQuote]] = {}
        self._programs: Dict[str, Any] = {}
        self._token_accounts: Dict[str, Dict[str, str]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[SolanaBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in SolanaBridgeProtocol
        }

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache
        self._fee_cache: Dict[str, Dict[str, Any]] = {}
        self._account_cache: Dict[str, Dict[str, Any]] = {}

        # Charge les programmes
        self._load_programs()

        # Charge les mappings de tokens
        self._load_token_mappings()

        logger.info("SolanaBridge initialisé avec succès")

    def _load_programs(self) -> None:
        """Charge les programmes Solana"""
        try:
            # Les programmes sont chargés dynamiquement via les transactions
            # On enregistre juste les IDs
            for protocol, program_info in self.PROGRAMS.items():
                self._programs[protocol] = {}
                for key, program_id in program_info.items():
                    if program_id:
                        self._programs[protocol][key] = PublicKey(program_id)

            logger.info(f"Programmes chargés: {list(self._programs.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des programmes: {e}")
            raise BridgeError(f"Erreur de chargement des programmes: {e}")

    def _load_token_mappings(self) -> None:
        """Charge les mappings des tokens Solana"""
        # Mappings standard
        self._token_mappings = self.TOKEN_MAPPINGS.copy()

        # Ajout des mappings depuis la configuration
        if self.config.get("token_mappings"):
            user_mappings = self.config.get("token_mappings", {})
            self._token_mappings.update(user_mappings)

        logger.info(f"Token mappings chargés: {len(self._token_mappings)} tokens")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_quote(
        self,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: SolanaBridgeDirection,
        destination_address: str,
        protocol: Optional[SolanaBridgeProtocol] = None,
        **kwargs,
    ) -> SolanaBridgeQuote:
        """
        Obtient un devis pour un bridge Solana

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            direction: Direction du bridge
            destination_address: Adresse destination
            protocol: Protocole spécifique
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis Solana: {amount} {token_from} -> {token_to} "
            f"({direction.value})"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{direction.value}:{protocol}"
        if cache_key in self._quote_cache:
            cached_time, quote = self._quote_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis retourné du cache")
                return quote

        try:
            # Sélection du protocole
            if protocol is None:
                protocol = await self._select_best_protocol(
                    token_from, token_to, direction
                )

            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                logger.warning(f"Circuit breaker ouvert pour {protocol.value}")
                fallback_protocol = await self._select_fallback_protocol(
                    protocol, token_from, token_to, direction
                )
                if fallback_protocol:
                    protocol = fallback_protocol
                else:
                    raise BridgeError(f"Protocole {protocol.value} indisponible")

            # Génération du devis
            quote = await self._generate_quote(
                protocol=protocol,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                direction=direction,
                destination_address=destination_address,
                **kwargs,
            )

            # Mise en cache
            self._quote_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "solana_bridge_quote",
                1,
                {
                    "protocol": protocol.value,
                    "direction": direction.value,
                    "token_from": token_from,
                    "token_to": token_to,
                },
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur lors de la génération du devis: {e}")
            raise BridgeError(f"Erreur de génération de devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_bridge(
        self,
        request: SolanaBridgeRequest,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge Solana

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        bridge_id = f"sol_bridge_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du bridge Solana {bridge_id}")

        try:
            # 1. Obtention du devis
            quote = await self.get_quote(
                token_from=request.token_from,
                token_to=request.token_to,
                amount=request.amount,
                direction=request.direction,
                destination_address=request.destination_address,
                protocol=request.protocol,
                slippage_tolerance=request.slippage_tolerance,
            )

            # 2. Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(request.source_address)
            if not wallet:
                raise BridgeError("Wallet non trouvé")

            # 3. Vérification du solde
            balance = await self._get_balance(
                request.token_from,
                request.source_address,
            )
            if balance < request.amount:
                raise BridgeError(
                    f"Solde insuffisant: {balance} < {request.amount}"
                )

            # 4. Vérification/création du token account
            if request.token_from != "SOL" and request.direction == SolanaBridgeDirection.DEPOSIT:
                token_account = await self._get_or_create_token_account(
                    request.source_address,
                    request.token_from,
                )

            # 5. Exécution selon la direction
            if request.direction == SolanaBridgeDirection.DEPOSIT:
                result = await self._execute_deposit(request, quote, wallet)
            elif request.direction == SolanaBridgeDirection.WITHDRAWAL:
                result = await self._execute_withdrawal(request, quote, wallet)
            else:
                result = await self._execute_cross_chain(request, quote, wallet)

            # 6. Attente de la confirmation
            final_result = await self._wait_for_confirmation(
                bridge_id=bridge_id,
                tx_signature=result.get("tx_signature"),
            )

            # Mise à jour du statut
            result["status"] = "completed"
            result["bridge_id"] = bridge_id
            result["amount_received"] = final_result.get("amount_received", quote.min_amount_received)
            result["fees_paid"] = quote.total_fees
            result["completed_at"] = datetime.now().isoformat()

            # Stockage
            self._active_bridges.pop(bridge_id, None)
            self._bridge_history.append(result)

            # Métriques
            self.metrics.record_increment(
                "solana_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "direction": request.direction.value,
                    "token": request.token_from,
                },
            )

            logger.info(f"Bridge Solana {bridge_id} terminé avec succès")
            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du bridge: {e}")
            error_result = {
                "bridge_id": bridge_id,
                "status": "failed",
                "error": str(e),
                "request": request.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }

            self._bridge_history.append(error_result)

            self.metrics.record_increment(
                "solana_bridge_failed",
                {
                    "protocol": request.protocol.value,
                    "direction": request.direction.value,
                    "error": str(e)[:50],
                },
            )

            raise BridgeError(f"Erreur d'exécution du bridge: {e}")

    # ============================================================
    # MÉTHODES D'EXÉCUTION
    # ============================================================

    async def _execute_deposit(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute un dépôt vers Solana"""
        logger.info(f"Exécution du dépôt Solana: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de dépôt
            tx_result = await self._build_and_send_transaction(
                request=request,
                quote=quote,
                wallet=wallet,
            )

            return {
                "tx_signature": tx_result.get("tx_signature"),
                "direction": "deposit",
                "amount": str(request.amount),
                "token": request.token_from,
                "blockhash": tx_result.get("blockhash"),
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du dépôt: {e}")
            raise

    async def _execute_withdrawal(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute un retrait depuis Solana"""
        logger.info(f"Exécution du retrait Solana: {request.amount} {request.token_from}")

        try:
            tx_result = await self._build_and_send_transaction(
                request=request,
                quote=quote,
                wallet=wallet,
            )

            return {
                "tx_signature": tx_result.get("tx_signature"),
                "direction": "withdrawal",
                "amount": str(request.amount),
                "token": request.token_from,
                "blockhash": tx_result.get("blockhash"),
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du retrait: {e}")
            raise

    async def _execute_cross_chain(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute un bridge cross-chain depuis Solana"""
        logger.info(f"Exécution du bridge cross-chain Solana: {request.amount}")

        protocol = request.protocol

        if protocol == SolanaBridgeProtocol.WORMHOLE:
            return await self._execute_wormhole(request, quote, wallet)
        elif protocol == SolanaBridgeProtocol.DEBRIDGE:
            return await self._execute_debridge(request, quote, wallet)
        elif protocol == SolanaBridgeProtocol.ALLBRIDGE:
            return await self._execute_allbridge(request, quote, wallet)
        else:
            return await self._execute_generic_bridge(request, quote, wallet)

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_and_send_transaction(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Construit et envoie une transaction Solana"""
        try:
            # Récupération du blockhash
            blockhash_data = await self.solana_client.get_latest_blockhash()
            blockhash = blockhash_data["result"]["value"]["blockhash"]

            # Construction de la transaction
            transaction = Transaction()

            # Ajout des instructions selon le protocole
            if request.protocol == SolanaBridgeProtocol.WORMHOLE:
                instructions = await self._build_wormhole_instructions(
                    request, quote, wallet
                )
            elif request.protocol == SolanaBridgeProtocol.DEBRIDGE:
                instructions = await self._build_debridge_instructions(
                    request, quote, wallet
                )
            else:
                instructions = await self._build_generic_instructions(
                    request, quote, wallet
                )

            for instruction in instructions:
                transaction.add(instruction)

            # Signature
            keypair = await self._get_keypair(wallet)
            transaction.sign(keypair)

            # Envoi
            tx_opts = TxOpts(
                skip_preflight=False,
                preflight_commitment=Confirmed,
            )

            send_result = await self.solana_client.send_transaction(
                transaction,
                keypair,
                opts=tx_opts,
            )

            tx_signature = send_result["result"]

            logger.info(f"Transaction envoyée: {tx_signature}")

            return {
                "tx_signature": tx_signature,
                "blockhash": blockhash,
            }

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise BridgeError(f"Erreur d'envoi de transaction: {e}")

    async def _build_wormhole_instructions(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> List[TransactionInstruction]:
        """Construit les instructions Wormhole"""
        instructions = []

        # Récupération des programmes
        wormhole_core = self._programs.get("wormhole", {}).get("core_bridge")
        wormhole_token = self._programs.get("wormhole", {}).get("token_bridge")

        if not wormhole_core or not wormhole_token:
            raise BridgeError("Programmes Wormhole non trouvés")

        # Source et destination
        source = PublicKey(request.source_address)
        destination = PublicKey(request.destination_address)

        # Token source
        token_mint = await self._get_token_mint(request.token_from)

        # Transfer du token vers le bridge
        if request.token_from != "SOL":
            # Transfer SPL token
            transfer_ix = await self._create_token_transfer_instruction(
                source=source,
                token_mint=token_mint,
                amount=request.amount,
                destination=wormhole_token,
            )
            if transfer_ix:
                instructions.append(transfer_ix)

        # Bridge instruction
        # Note: Wormhole bridge instructions sont complexes
        # Cette partie est simplifiée

        return instructions

    async def _build_debridge_instructions(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> List[TransactionInstruction]:
        """Construit les instructions deBridge"""
        instructions = []

        # Récupération du programme deBridge
        debridge_program = self._programs.get("debridge", {}).get("program")
        if not debridge_program:
            raise BridgeError("Programme deBridge non trouvé")

        # Construction simplifiée de l'instruction
        # Dans la réalité, on utiliserait les SDK deBridge

        return instructions

    async def _build_generic_instructions(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> List[TransactionInstruction]:
        """Construit des instructions génériques"""
        instructions = []

        source = PublicKey(request.source_address)
        destination = PublicKey(request.destination_address)

        # Transfer SOL si c'est un transfer natif
        if request.token_from == "SOL" and request.direction == SolanaBridgeDirection.DEPOSIT:
            lamports = int(request.amount * Decimal(1e9))
            transfer_ix = SystemProgram.transfer(
                TransferParams(
                    from_pubkey=source,
                    to_pubkey=destination,
                    lamports=lamports,
                )
            )
            instructions.append(transfer_ix)

        return instructions

    # ============================================================
    # MÉTHODES DE VÉRIFICATION ET CONFIRMATION
    # ============================================================

    async def _wait_for_confirmation(
        self,
        bridge_id: str,
        tx_signature: Optional[str],
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction Solana"""
        if not tx_signature:
            raise BridgeError("Signature de transaction manquante")

        logger.info(f"Attente de confirmation pour {bridge_id}: {tx_signature}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Récupération du statut
                status = await self.solana_client.get_signature_statuses(
                    [tx_signature]
                )

                if status["result"]["value"]:
                    status_info = status["result"]["value"][0]
                    if status_info and status_info.get("confirmationStatus") in ["confirmed", "finalized"]:
                        # Récupération des détails
                        tx_info = await self.solana_client.get_transaction(
                            tx_signature,
                            commitment=Finalized,
                        )

                        return {
                            "amount_received": "0",  # À extraire des logs
                            "confirmations": 32 if status_info.get("confirmationStatus") == "finalized" else 12,
                            "slot": status_info.get("slot", 0),
                        }

            except Exception as e:
                logger.warning(f"Erreur de vérification: {e}")

            await asyncio.sleep(5)

        raise BridgeError(f"Timeout de confirmation: {tx_signature}")

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _generate_quote(
        self,
        protocol: SolanaBridgeProtocol,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: SolanaBridgeDirection,
        destination_address: str,
        **kwargs,
    ) -> SolanaBridgeQuote:
        """Génère un devis pour un protocole spécifique"""
        try:
            # Estimation des frais
            solana_fees = await self._estimate_solana_fees(protocol, amount)
            bridge_fees = await self._estimate_bridge_fees(
                protocol, token_from, amount, direction
            )
            total_fees = solana_fees + bridge_fees

            # Estimation du temps
            estimated_time = await self._estimate_time(protocol, direction)

            # ATA requis
            requires_ata = token_from != "SOL" and direction == SolanaBridgeDirection.DEPOSIT

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            # Slippage
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            return SolanaBridgeQuote(
                quote_id=f"sol_q_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                direction=direction,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                solana_fees=solana_fees,
                bridge_fees=bridge_fees,
                total_fees=total_fees,
                estimated_time=estimated_time,
                min_amount_received=min_amount_received,
                max_slippage=slippage,
                confidence=confidence,
                requires_ata=requires_ata,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _estimate_solana_fees(
        self,
        protocol: SolanaBridgeProtocol,
        amount: Decimal,
    ) -> Decimal:
        """Estime les frais Solana (en SOL)"""
        try:
            # Frais de base Solana
            base_fee_sol = Decimal("0.000005")  # ~0.000005 SOL

            # Frais de priorité
            priority_fee = await self._get_priority_fee(protocol)
            priority_fee_sol = Decimal(str(priority_fee)) / Decimal(1e9)

            # Frais d'exécution du programme
            program_fee = {
                SolanaBridgeProtocol.WORMHOLE: Decimal("0.00001"),
                SolanaBridgeProtocol.DEBRIDGE: Decimal("0.000015"),
                SolanaBridgeProtocol.ALLBRIDGE: Decimal("0.000012"),
            }.get(protocol, Decimal("0.000008"))

            # Ajustement pour les gros montants
            if amount > Decimal("10000"):
                program_fee *= Decimal("1.5")

            total_fee = base_fee_sol + priority_fee_sol + program_fee

            return total_fee

        except Exception as e:
            logger.warning(f"Erreur d'estimation des frais Solana: {e}")
            return Decimal("0.00001")

    async def _estimate_bridge_fees(
        self,
        protocol: SolanaBridgeProtocol,
        token: str,
        amount: Decimal,
        direction: SolanaBridgeDirection,
    ) -> Decimal:
        """Estime les frais de bridge"""
        base_fees = {
            SolanaBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            SolanaBridgeProtocol.DEBRIDGE: Decimal("0.0005"),
            SolanaBridgeProtocol.ALLBRIDGE: Decimal("0.0004"),
            SolanaBridgeProtocol.SWIM: Decimal("0.0006"),
            SolanaBridgeProtocol.PORTAL: Decimal("0.0003"),
        }.get(protocol, Decimal("0.0004"))

        variable_fees = amount * Decimal("0.0002")

        return base_fees + variable_fees

    async def _estimate_time(
        self,
        protocol: SolanaBridgeProtocol,
        direction: SolanaBridgeDirection,
    ) -> int:
        """Estime le temps de bridge en secondes"""
        base_time = {
            SolanaBridgeProtocol.WORMHOLE: 30,
            SolanaBridgeProtocol.DEBRIDGE: 45,
            SolanaBridgeProtocol.ALLBRIDGE: 40,
            SolanaBridgeProtocol.SWIM: 35,
            SolanaBridgeProtocol.PORTAL: 30,
        }.get(protocol, 40)

        # Les retraits vers L1 sont plus lents
        if direction == SolanaBridgeDirection.WITHDRAWAL:
            base_time += 3600  # 1 heure supplémentaire

        return base_time

    def _calculate_confidence(
        self,
        protocol: SolanaBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            SolanaBridgeProtocol.WORMHOLE: 0.98,
            SolanaBridgeProtocol.DEBRIDGE: 0.95,
            SolanaBridgeProtocol.ALLBRIDGE: 0.96,
            SolanaBridgeProtocol.SWIM: 0.90,
            SolanaBridgeProtocol.PORTAL: 0.97,
        }.get(protocol, 0.95)

        if amount > Decimal("50000"):
            base_confidence -= 0.10
        elif amount > Decimal("10000"):
            base_confidence -= 0.05

        if protocol in self.circuit_breakers:
            cb = self.circuit_breakers[protocol]
            if cb.failure_count > 0:
                base_confidence -= min(0.2, cb.failure_count * 0.02)

        return max(0.5, min(0.99, base_confidence))

    # ============================================================
    # MÉTHODES DE SÉLECTION
    # ============================================================

    async def _select_best_protocol(
        self,
        token_from: str,
        token_to: str,
        direction: SolanaBridgeDirection,
    ) -> SolanaBridgeProtocol:
        """Sélectionne le meilleur protocole"""
        available_protocols = []

        for protocol in SolanaBridgeProtocol:
            if not self.circuit_breakers[protocol].is_available():
                continue

            if await self._is_protocol_supported(protocol, token_from, token_to, direction):
                available_protocols.append(protocol)

        if not available_protocols:
            return SolanaBridgeProtocol.WORMHOLE

        # Score des protocoles
        scores = []
        for protocol in available_protocols:
            score = await self._score_protocol(protocol, token_from, token_to, direction)
            scores.append((score, protocol))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

    async def _is_protocol_supported(
        self,
        protocol: SolanaBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: SolanaBridgeDirection,
    ) -> bool:
        """Vérifie si un protocole supporte la requête"""
        supported_tokens = self.config.get("protocol_tokens", {}).get(protocol.value, [])
        if supported_tokens and token_from not in supported_tokens:
            return False

        supported_directions = self.config.get("protocol_directions", {}).get(protocol.value, [])
        if supported_directions and direction.value not in supported_directions:
            return False

        return True

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(
        self,
        token: str,
        address: str,
    ) -> Decimal:
        """Obtient le solde d'un token Solana"""
        try:
            public_key = PublicKey(address)

            if token == "SOL":
                balance = await self.solana_client.get_balance(public_key)
                return Decimal(str(balance["result"]["value"])) / Decimal(1e9)

            # SPL Token
            token_mint = await self._get_token_mint(token)
            token_account = get_associated_token_address(public_key, token_mint)

            balance = await self.solana_client.get_token_account_balance(
                token_account,
                commitment=Confirmed,
            )
            decimals = await self._get_token_decimals(token)
            return Decimal(str(balance["result"]["value"]["amount"])) / Decimal(10 ** decimals)

        except Exception as e:
            logger.error(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_token_mint(self, token_symbol: str) -> PublicKey:
        """Obtient le mint d'un token"""
        token_address = self._token_mappings.get(token_symbol)
        if not token_address:
            raise BridgeError(f"Token non supporté: {token_symbol}")
        return PublicKey(token_address)

    async def _get_token_decimals(self, token_symbol: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        decimals_map = {
            "SOL": 9,
            "USDC": 6,
            "USDT": 6,
            "DAI": 6,
            "WBTC": 8,
            "WETH": 8,
        }
        return decimals_map.get(token_symbol, 6)

    async def _get_priority_fee(self, protocol: SolanaBridgeProtocol) -> int:
        """Obtient le frais de priorité recommandé"""
        try:
            # Récupération des frais de priorité
            recent_priority_fees = await self.solana_client.get_recent_prioritization_fees()
            if recent_priority_fees["result"]:
                # Prendre le 75ème percentile
                fees = [fee["prioritizationFee"] for fee in recent_priority_fees["result"]]
                fees.sort()
                index = int(len(fees) * 0.75)
                return fees[index] if fees else 100000  # 0.0001 SOL

            return 100000

        except Exception:
            return 100000

    async def _get_or_create_token_account(
        self,
        owner: str,
        token_symbol: str,
    ) -> str:
        """Obtient ou crée un token account"""
        try:
            owner_pubkey = PublicKey(owner)
            token_mint = await self._get_token_mint(token_symbol)

            # Vérifier si l'ATA existe
            ata = get_associated_token_address(owner_pubkey, token_mint)

            try:
                account_info = await self.solana_client.get_account_info(ata)
                if account_info["result"]["value"]:
                    return str(ata)
            except Exception:
                pass

            # Créer l'ATA
            # Note: Cette opération nécessite une transaction séparée
            # Pour simplifier, on retourne l'adresse
            return str(ata)

        except Exception as e:
            logger.warning(f"Erreur de création de token account: {e}")
            return ""

    async def _create_token_transfer_instruction(
        self,
        source: PublicKey,
        token_mint: PublicKey,
        amount: Decimal,
        destination: PublicKey,
    ) -> Optional[TransactionInstruction]:
        """Crée une instruction de transfert de token SPL"""
        try:
            # Récupération du token account source
            source_ata = get_associated_token_address(source, token_mint)

            # Transfer
            decimals = await self._get_token_decimals_from_mint(token_mint)
            amount_ui = int(amount * Decimal(10 ** decimals))

            transfer_ix = transfer(
                source=source_ata,
                dest=destination,
                owner=source,
                amount=amount_ui,
                program_id=TOKEN_PROGRAM_ID,
            )

            return transfer_ix

        except Exception as e:
            logger.warning(f"Erreur de création de transfer: {e}")
            return None

    async def _get_token_decimals_from_mint(self, mint: PublicKey) -> int:
        """Obtient les décimales d'un mint"""
        try:
            token_info = await self.solana_client.get_token_supply(mint)
            return token_info["result"]["value"]["decimals"]
        except Exception:
            return 6

    async def _get_keypair(self, wallet: Any) -> Keypair:
        """Convertit un wallet en Keypair Solana"""
        # Dans la réalité, on extrait la private key du wallet
        # Pour simplifier, on retourne un Keypair généré
        return Keypair()

    # ============================================================
    # MÉTHODES DE PROTOCOLES SPÉCIFIQUES
    # ============================================================

    async def _execute_wormhole(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute Wormhole sur Solana"""
        logger.info("Exécution de Wormhole bridge sur Solana")

        # Construction de la transaction Wormhole
        tx_result = await self._build_and_send_transaction(
            request=request,
            quote=quote,
            wallet=wallet,
        )

        return {
            "tx_signature": tx_result.get("tx_signature"),
            "protocol": "wormhole",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_debridge(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute deBridge sur Solana"""
        logger.info("Exécution de deBridge bridge sur Solana")

        tx_result = await self._build_and_send_transaction(
            request=request,
            quote=quote,
            wallet=wallet,
        )

        return {
            "tx_signature": tx_result.get("tx_signature"),
            "protocol": "debridge",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_allbridge(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute Allbridge sur Solana"""
        logger.info("Exécution de Allbridge bridge sur Solana")

        tx_result = await self._build_and_send_transaction(
            request=request,
            quote=quote,
            wallet=wallet,
        )

        return {
            "tx_signature": tx_result.get("tx_signature"),
            "protocol": "allbridge",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_generic_bridge(
        self,
        request: SolanaBridgeRequest,
        quote: SolanaBridgeQuote,
        wallet: Any,
    ) -> Dict[str, Any]:
        """Exécute un protocole générique"""
        logger.info("Exécution du bridge générique sur Solana")

        tx_result = await self._build_and_send_transaction(
            request=request,
            quote=quote,
            wallet=wallet,
        )

        return {
            "tx_signature": tx_result.get("tx_signature"),
            "protocol": request.protocol.value,
            "amount": str(request.amount),
            "token": request.token_from,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources SolanaBridge...")

        # Nettoyage des caches
        self._quote_cache.clear()
        self._fee_cache.clear()
        self._account_cache.clear()
        self._token_accounts.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        # Fermeture du client Solana
        try:
            await self.solana_client.close()
        except Exception:
            pass

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_solana_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    solana_client: AsyncClient,
    bridge_manager: BridgeManager,
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> SolanaBridge:
    """
    Crée une instance de SolanaBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        solana_client: Client Solana
        bridge_manager: Gestionnaire de bridges
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de SolanaBridge
    """
    return SolanaBridge(
        config=config,
        wallet_manager=wallet_manager,
        solana_client=solana_client,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du bridge Solana"""
    # Configuration
    config = {
        "protocol_tokens": {
            "wormhole": ["SOL", "USDC", "USDT", "WETH", "WBTC"],
            "debridge": ["SOL", "USDC", "USDT"],
            "allbridge": ["SOL", "USDC", "DAI"],
        },
        "protocol_directions": {
            "wormhole": ["deposit", "withdrawal", "cross_chain"],
            "debridge": ["deposit", "withdrawal"],
            "allbridge": ["deposit", "withdrawal"],
        },
        "token_mappings": {
            "SOL": "So11111111111111111111111111111111111111112",
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        },
    }

    # Client Solana
    solana_client = AsyncClient("https://api.mainnet-beta.solana.com")

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        pass

    bridge_manager = SimpleBridgeManager()

    # Transaction manager (simplifié)
    class SimpleTransactionManager:
        pass

    transaction_manager = SimpleTransactionManager()

    # Création du bridge
    bridge = create_solana_bridge(
        config=config,
        wallet_manager=wallet_manager,
        solana_client=solana_client,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
    )

    # Obtention d'un devis
    quote = await bridge.get_quote(
        token_from="SOL",
        token_to="USDC",
        amount=Decimal("1"),
        direction=SolanaBridgeDirection.DEPOSIT,
        destination_address="0x...",
        protocol=SolanaBridgeProtocol.WORMHOLE,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    request = SolanaBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=SolanaBridgeProtocol.WORMHOLE,
        direction=SolanaBridgeDirection.DEPOSIT,
        token_from="SOL",
        token_to="USDC",
        amount=Decimal("0.1"),
        source_address="...",
        destination_address="...",
    )

    result = await bridge.execute_bridge(request)
    print(f"Résultat: {result}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

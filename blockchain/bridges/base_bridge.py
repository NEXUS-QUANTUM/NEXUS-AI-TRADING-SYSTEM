# blockchain/bridges/base_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Base Bridge

Ce module définit la classe de base abstraite pour tous les bridges cross-chain,
fournissant l'interface commune, les fonctionnalités partagées, et les
mécanismes de base pour les opérations de bridge.

Fonctionnalités principales:
- Interface unifiée pour tous les bridges
- Gestion des transactions de base
- Validation des paramètres
- Gestion des erreurs communes
- Logging et monitoring
- Métriques de base
- Support des retries
- Gestion des timeouts
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
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
from functools import wraps

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES DE BASE
# ============================================================

class BridgeStatus(Enum):
    """Statuts de base d'un bridge"""
    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class BridgeType(Enum):
    """Types de base de bridge"""
    LOCK_AND_MINT = "lock_and_mint"
    BURN_AND_MINT = "burn_and_mint"
    LOCK_AND_UNLOCK = "lock_and_unlock"
    SWAP = "swap"
    NATIVE = "native"


class TransactionStatus(Enum):
    """Statuts de base de transaction"""
    PENDING = "pending"
    SIGNING = "signing"
    BROADCASTING = "broadcasting"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"
    CANCELLED = "cancelled"


@dataclass
class BaseBridgeConfig:
    """Configuration de base pour un bridge"""
    name: str
    protocol: str
    chain: str
    type: BridgeType
    status: BridgeStatus
    contract_address: str
    supported_tokens: List[str]
    min_amount: Decimal
    max_amount: Decimal
    gas_limit: int
    confirmations_required: int
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BaseBridgeQuote:
    """Devis de base pour un bridge"""
    quote_id: str
    protocol: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    estimated_gas: Decimal
    estimated_fees: Decimal
    estimated_time: int
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "estimated_gas": str(self.estimated_gas),
            "estimated_fees": str(self.estimated_fees),
            "estimated_time": self.estimated_time,
            "min_amount_received": str(self.min_amount_received),
            "max_slippage": str(self.max_slippage),
            "confidence": self.confidence,
        }


@dataclass
class BaseBridgeRequest:
    """Requête de base pour un bridge"""
    request_id: str
    protocol: str
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    destination_chain: str
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    use_fallback: bool = True
    max_gas_price: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BaseBridgeResult:
    """Résultat de base pour un bridge"""
    bridge_id: str
    request_id: str
    status: TransactionStatus
    protocol: str
    tx_hash: Optional[str] = None
    bridge_tx_id: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    amount_received: Optional[Decimal] = None
    fees_total: Optional[Decimal] = None
    gas_used: Optional[Decimal] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "bridge_id": self.bridge_id,
            "request_id": self.request_id,
            "status": self.status.value,
            "protocol": self.protocol,
            "tx_hash": self.tx_hash,
            "bridge_tx_id": self.bridge_tx_id,
            "amount_in": str(self.amount_in) if self.amount_in else None,
            "amount_out": str(self.amount_out) if self.amount_out else None,
            "amount_received": str(self.amount_received) if self.amount_received else None,
            "fees_total": str(self.fees_total) if self.fees_total else None,
            "gas_used": str(self.gas_used) if self.gas_used else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


# ============================================================
# CLASSE DE BASE ABSTRAITE
# ============================================================

class BaseBridge(ABC):
    """
    Classe de base abstraite pour tous les bridges
    """

    # ABI ERC-20 de base
    ERC20_ABI = [
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
            "constant": False,
            "inputs": [
                {"name": "sender", "type": "address"},
                {"name": "recipient", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "transferFrom",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
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
    ]

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialise le bridge de base

        Args:
            config: Configuration du bridge
            wallet_manager: Gestionnaire de wallets
            metrics_collector: Collecteur de métriques
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.metrics = metrics_collector or MetricsCollector()

        # Configuration de base
        self.name = config.get("name", "BaseBridge")
        self.protocol = config.get("protocol", "base")
        self.chain = config.get("chain", "ethereum")
        self.enabled = config.get("enabled", True)
        self.status = BridgeStatus(config.get("status", "active"))

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=config.get("max_retries", 3),
            initial_delay=config.get("retry_delay", 1.0),
            max_delay=config.get("max_retry_delay", 30.0),
            backoff=config.get("retry_backoff", 2.0),
        )

        # État interne
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._operation_history: List[Dict[str, Any]] = []

        # Thread pool pour les opérations synchrones
        self._executor = ThreadPoolExecutor(max_workers=config.get("max_workers", 10))

        # Métriques de base
        self._operation_count = 0
        self._success_count = 0
        self._failure_count = 0

        logger.info(f"BaseBridge {self.name} initialisé")

    # ============================================================
    # MÉTHODES ABSTRAITES (À IMPLÉMENTER)
    # ============================================================

    @abstractmethod
    async def get_quote(
        self,
        token_from: str,
        token_to: str,
        amount: Decimal,
        destination_chain: str,
        destination_address: str,
        **kwargs,
    ) -> BaseBridgeQuote:
        """
        Obtient un devis pour un bridge

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant
            destination_chain: Chaîne destination
            destination_address: Adresse destination
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        pass

    @abstractmethod
    async def execute_bridge(
        self,
        request: BaseBridgeRequest,
    ) -> BaseBridgeResult:
        """
        Exécute un bridge

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        pass

    @abstractmethod
    async def get_bridge_status(
        self,
        bridge_id: str,
    ) -> Optional[BaseBridgeResult]:
        """
        Obtient le statut d'un bridge

        Args:
            bridge_id: ID du bridge

        Returns:
            Résultat du bridge ou None
        """
        pass

    @abstractmethod
    async def cancel_bridge(
        self,
        bridge_id: str,
    ) -> bool:
        """
        Annule un bridge en cours

        Args:
            bridge_id: ID du bridge

        Returns:
            True si annulé avec succès
        """
        pass

    # ============================================================
    # MÉTHODES DE BASE COMMUNES
    # ============================================================

    async def validate_request(self, request: BaseBridgeRequest) -> bool:
        """
        Valide une requête de bridge

        Args:
            request: Requête à valider

        Returns:
            True si valide

        Raises:
            ValidationError: Si la requête est invalide
        """
        # Vérification du montant
        if request.amount <= Decimal("0"):
            raise ValidationError("Le montant doit être positif")

        # Vérification des adresses
        if not request.source_address or not request.destination_address:
            raise ValidationError("Adresses source et destination requises")

        # Vérification des tokens
        if not request.token_from or not request.token_to:
            raise ValidationError("Tokens source et destination requis")

        # Vérification des limites
        min_amount = self.config.get("min_amount", Decimal("0.001"))
        max_amount = self.config.get("max_amount", Decimal("1000000"))

        if request.amount < min_amount:
            raise ValidationError(
                f"Montant inférieur au minimum ({min_amount})"
            )

        if request.amount > max_amount:
            raise ValidationError(
                f"Montant supérieur au maximum ({max_amount})"
            )

        # Vérification du slippage
        if request.slippage_tolerance > Decimal("0.1"):
            raise ValidationError(
                "Tolérance de slippage trop élevée (max 10%)"
            )

        return True

    async def handle_error(
        self,
        error: Exception,
        operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gère une erreur

        Args:
            error: Erreur à gérer
            operation_id: ID de l'opération

        Returns:
            Informations sur l'erreur
        """
        error_info = {
            "operation_id": operation_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
        }

        # Logging
        if isinstance(error, (BridgeError, TransactionError, ValidationError)):
            logger.warning(f"Erreur de bridge: {error}")
        else:
            logger.error(f"Erreur inattendue: {error}", exc_info=True)

        # Métriques
        self._failure_count += 1
        self.metrics.record_increment(
            "bridge_error",
            1,
            {
                "protocol": self.protocol,
                "chain": self.chain,
                "error_type": type(error).__name__,
            },
        )

        return error_info

    async def log_operation(
        self,
        operation_id: str,
        operation_type: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Logge une opération

        Args:
            operation_id: ID de l'opération
            operation_type: Type d'opération
            details: Détails de l'opération
        """
        log_entry = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "protocol": self.protocol,
            "chain": self.chain,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }

        self._operation_history.append(log_entry)

        # Conservation limitée
        if len(self._operation_history) > 10000:
            self._operation_history = self._operation_history[-5000:]

        logger.debug(f"Opération loggée: {operation_id}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques du bridge

        Returns:
            Statistiques
        """
        total_operations = self._operation_count
        success_rate = self._success_count / max(1, total_operations)

        return {
            "name": self.name,
            "protocol": self.protocol,
            "chain": self.chain,
            "status": self.status.value,
            "enabled": self.enabled,
            "total_operations": total_operations,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "active_operations": len(self._active_operations),
            "history_size": len(self._operation_history),
        }

    def get_config(self) -> Dict[str, Any]:
        """
        Obtient la configuration du bridge

        Returns:
            Configuration
        """
        return {
            "name": self.name,
            "protocol": self.protocol,
            "chain": self.chain,
            "enabled": self.enabled,
            "status": self.status.value,
            "min_amount": str(self.config.get("min_amount", "0.001")),
            "max_amount": str(self.config.get("max_amount", "1000000")),
            "gas_limit": self.config.get("gas_limit", 200000),
            "confirmations_required": self.config.get("confirmations_required", 12),
            "supported_tokens": self.config.get("supported_tokens", []),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """
        Nettoie les ressources

        Cette méthode doit être appelée lors de l'arrêt du bridge
        """
        logger.info(f"Nettoyage du bridge {self.name}")

        # Nettoyage des opérations actives
        for operation_id in list(self._active_operations.keys()):
            try:
                await self.cancel_bridge(operation_id)
            except Exception as e:
                logger.warning(f"Erreur d'annulation de {operation_id}: {e}")

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info(f"Bridge {self.name} nettoyé")

    # ============================================================
    # MÉTHODES UTILITAIRES PROTÉGÉES
    # ============================================================

    def _generate_operation_id(self) -> str:
        """Génère un ID d'opération unique"""
        return f"op_{uuid.uuid4().hex[:12]}"

    def _get_token_decimals(self, token: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        # Par défaut, 18 décimales pour la plupart des tokens
        decimals_map = {
            "ETH": 18,
            "USDC": 6,
            "USDT": 6,
            "DAI": 18,
            "WBTC": 8,
            "BNB": 18,
            "MATIC": 18,
            "SOL": 9,
        }
        return decimals_map.get(token, 18)

    def _format_amount(self, amount: Decimal, decimals: int) -> int:
        """Formate un montant en wei"""
        return int(amount * Decimal(10 ** decimals))

    def _unformat_amount(self, amount: int, decimals: int) -> Decimal:
        """Déformate un montant depuis wei"""
        return Decimal(str(amount)) / Decimal(10 ** decimals)

    def _is_native_token(self, token: str) -> bool:
        """Vérifie si un token est natif"""
        native_tokens = ["ETH", "BNB", "MATIC", "SOL", "AVAX", "BNB"]
        return token in native_tokens

    async def _sleep(self, seconds: float) -> None:
        """Attend le nombre de secondes spécifié"""
        await asyncio.sleep(seconds)

    # ============================================================
    # MÉTHODES DE CONTEXTE
    # ============================================================

    async def __aenter__(self):
        """Support du contexte async"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support du contexte async"""
        await self.cleanup()


# ============================================================
# DÉCORATEURS UTILITAIRES
# ============================================================

def log_operation(operation_type: str):
    """
    Décorateur pour logger les opérations

    Args:
        operation_type: Type d'opération
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            operation_id = self._generate_operation_id()
            self._operation_count += 1

            try:
                # Log de début
                await self.log_operation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    details={"action": "start", "args": str(args)[:200]},
                )

                # Exécution
                result = await func(self, *args, **kwargs)

                # Log de succès
                self._success_count += 1
                await self.log_operation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    details={"action": "success", "result": str(result)[:200]},
                )

                return result

            except Exception as e:
                # Log d'erreur
                await self.handle_error(e, operation_id)
                raise

        return wrapper
    return decorator


def measure_time():
    """
    Décorateur pour mesurer le temps d'exécution
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)
                elapsed = time.time() - start_time

                # Métriques
                self.metrics.record_timing(
                    f"bridge_{func.__name__}_time",
                    elapsed,
                    {"protocol": self.protocol, "chain": self.chain},
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.debug(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
                raise

        return wrapper
    return decorator


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de la classe de base"""
    # Configuration
    config = {
        "name": "ExampleBridge",
        "protocol": "example",
        "chain": "ethereum",
        "enabled": True,
        "min_amount": Decimal("0.001"),
        "max_amount": Decimal("1000000"),
        "gas_limit": 200000,
        "confirmations_required": 12,
        "supported_tokens": ["ETH", "USDC", "USDT"],
        "max_retries": 3,
        "retry_delay": 1.0,
    }

    # Création d'une implémentation de test
    class TestBridge(BaseBridge):
        async def get_quote(self, token_from, token_to, amount, destination_chain, destination_address, **kwargs):
            return BaseBridgeQuote(
                quote_id=f"q_{uuid.uuid4().hex[:8]}",
                protocol=self.protocol,
                chain_from=self.chain,
                chain_to=destination_chain,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                estimated_gas=Decimal("0.001"),
                estimated_fees=Decimal("0.0005"),
                estimated_time=60,
                min_amount_received=amount * Decimal("0.99"),
                max_slippage=Decimal("0.01"),
                confidence=0.95,
            )

        async def execute_bridge(self, request):
            return BaseBridgeResult(
                bridge_id=f"bridge_{uuid.uuid4().hex[:12]}",
                request_id=request.request_id,
                status=TransactionStatus.COMPLETED,
                protocol=self.protocol,
                tx_hash="0x...",
                amount_in=request.amount,
                amount_out=request.amount * Decimal("0.99"),
                amount_received=request.amount * Decimal("0.99"),
                fees_total=Decimal("0.0015"),
                gas_used=Decimal("0.001"),
                start_time=datetime.now(),
                end_time=datetime.now(),
            )

        async def get_bridge_status(self, bridge_id):
            return None

        async def cancel_bridge(self, bridge_id):
            return True

    # Utilisation
    bridge = TestBridge(config)

    # Validation d'une requête
    request = BaseBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol="example",
        token_from="ETH",
        token_to="USDC",
        amount=Decimal("1.0"),
        source_address="0x...",
        destination_address="0x...",
        destination_chain="polygon",
    )

    await bridge.validate_request(request)

    # Obtention d'un devis
    quote = await bridge.get_quote(
        token_from="ETH",
        token_to="USDC",
        amount=Decimal("1.0"),
        destination_chain="polygon",
        destination_address="0x...",
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    result = await bridge.execute_bridge(request)
    print(f"Résultat: {result.to_dict()}")

    # Statistiques
    stats = bridge.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

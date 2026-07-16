# blockchain/defi/base_protocol.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Base Protocol - Interface DeFi Générique

Ce module définit la classe de base abstraite pour tous les protocoles DeFi,
fournissant une interface unifiée pour les opérations de lending, borrowing,
staking, yield farming, et autres fonctionnalités DeFi.

Fonctionnalités principales:
- Interface unifiée pour tous les protocoles DeFi
- Gestion des positions
- Calcul des rendements
- Gestion des risques
- Monitoring des protocoles
- Métriques de performance
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
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ProtocolType(Enum):
    """Types de protocoles DeFi"""
    LENDING = "lending"
    BORROWING = "borrowing"
    STAKING = "staking"
    YIELD_FARMING = "yield_farming"
    DEX = "dex"
    DERIVATIVES = "derivatives"
    INSURANCE = "insurance"
    SYNTHETIC = "synthetic"
    OPTIONS = "options"
    PREDICTION = "prediction"


class ProtocolStatus(Enum):
    """Statuts d'un protocole"""
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"
    VULNERABLE = "vulnerable"
    OFFLINE = "offline"


class PositionType(Enum):
    """Types de positions DeFi"""
    SUPPLY = "supply"
    DEBT = "debt"
    STAKED = "staked"
    FARMING = "farming"
    LP = "lp"
    INSURANCE = "insurance"


class RiskLevel(Enum):
    """Niveaux de risque"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ProtocolConfig:
    """Configuration de base d'un protocole DeFi"""
    name: str
    protocol_type: ProtocolType
    chain: str
    contract_address: str
    status: ProtocolStatus
    supported_tokens: List[str]
    min_amount: Decimal
    max_amount: Decimal
    risk_level: RiskLevel
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "name": self.name,
            "protocol_type": self.protocol_type.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "status": self.status.value,
            "supported_tokens": self.supported_tokens,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "risk_level": self.risk_level.value,
            "enabled": self.enabled,
            "priority": self.priority,
        }


@dataclass
class Position:
    """Position DeFi"""
    position_id: str
    position_type: PositionType
    protocol: str
    chain: str
    token: str
    amount: Decimal
    value_usd: Decimal
    apy: Decimal
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "position_type": self.position_type.value,
            "protocol": self.protocol,
            "chain": self.chain,
            "token": self.token,
            "amount": str(self.amount),
            "value_usd": str(self.value_usd),
            "apy": str(self.apy),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class YieldData:
    """Données de rendement"""
    protocol: str
    chain: str
    token: str
    apy: Decimal
    apr: Decimal
    rewards: List[Dict[str, Any]]
    risk_level: RiskLevel
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol,
            "chain": self.chain,
            "token": self.token,
            "apy": str(self.apy),
            "apr": str(self.apr),
            "rewards": self.rewards,
            "risk_level": self.risk_level.value,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CLASSE DE BASE ABSTRAITE
# ============================================================

class BaseProtocol(ABC):
    """
    Classe de base abstraite pour tous les protocoles DeFi
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
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
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
        Initialise le protocole de base

        Args:
            config: Configuration du protocole
            wallet_manager: Gestionnaire de wallets
            metrics_collector: Collecteur de métriques
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.metrics = metrics_collector or MetricsCollector()

        # Configuration de base
        self.name = config.get("name", "BaseProtocol")
        self.protocol_type = ProtocolType(config.get("protocol_type", "lending"))
        self.chain = config.get("chain", "ethereum")
        self.enabled = config.get("enabled", True)
        self.status = ProtocolStatus(config.get("status", "active"))

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=config.get("max_retries", 3),
            initial_delay=config.get("retry_delay", 1.0),
            max_delay=config.get("max_retry_delay", 30.0),
            backoff=config.get("retry_backoff", 2.0),
        )

        # État interne
        self._positions: Dict[str, Position] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._operation_history: List[Dict[str, Any]] = []

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=config.get("max_workers", 10))

        # Métriques
        self._operation_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_value_locked = Decimal("0")

        # Callbacks
        self._alert_callbacks: List[Callable] = []

        logger.info(f"BaseProtocol {self.name} initialisé")

    # ============================================================
    # MÉTHODES ABSTRAITES (À IMPLÉMENTER)
    # ============================================================

    @abstractmethod
    async def get_positions(self, address: str) -> List[Position]:
        """
        Obtient les positions d'un utilisateur

        Args:
            address: Adresse de l'utilisateur

        Returns:
            Liste des positions
        """
        pass

    @abstractmethod
    async def get_yield_data(self, token: str) -> YieldData:
        """
        Obtient les données de rendement pour un token

        Args:
            token: Symbole du token

        Returns:
            Données de rendement
        """
        pass

    @abstractmethod
    async def get_protocol_health(self) -> Dict[str, Any]:
        """
        Obtient l'état de santé du protocole

        Returns:
            Données de santé
        """
        pass

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        token: str,
        amount: Decimal,
        address: str,
        **kwargs,
    ) -> str:
        """
        Exécute une action sur le protocole

        Args:
            action: Type d'action (supply, borrow, withdraw, etc.)
            token: Symbole du token
            amount: Montant
            address: Adresse de l'utilisateur
            **kwargs: Arguments additionnels

        Returns:
            Hash de la transaction
        """
        pass

    # ============================================================
    # MÉTHODES DE BASE COMMUNES
    # ============================================================

    async def validate_action(
        self,
        action: str,
        token: str,
        amount: Decimal,
        address: str,
        **kwargs,
    ) -> bool:
        """
        Valide une action

        Args:
            action: Type d'action
            token: Symbole du token
            amount: Montant
            address: Adresse de l'utilisateur
            **kwargs: Arguments additionnels

        Returns:
            True si valide

        Raises:
            ValidationError: Si l'action est invalide
        """
        # Vérification du montant
        if amount <= Decimal("0"):
            raise ValidationError("Le montant doit être positif")

        # Vérification de l'adresse
        if not address or len(address) != 42:
            raise ValidationError("Adresse invalide")

        # Vérification du token
        if token not in self.config.get("supported_tokens", []):
            raise ValidationError(f"Token {token} non supporté")

        # Vérification des limites
        min_amount = Decimal(str(self.config.get("min_amount", "0.001")))
        max_amount = Decimal(str(self.config.get("max_amount", "1000000")))

        if amount < min_amount:
            raise ValidationError(
                f"Montant inférieur au minimum ({min_amount})"
            )

        if amount > max_amount:
            raise ValidationError(
                f"Montant supérieur au maximum ({max_amount})"
            )

        # Vérification du statut du protocole
        if self.status != ProtocolStatus.ACTIVE:
            raise ValidationError(
                f"Protocole {self.status.value}, actions non disponibles"
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
        if isinstance(error, (DeFiError, ValidationError, TransactionError)):
            logger.warning(f"Erreur DeFi: {error}")
        else:
            logger.error(f"Erreur inattendue: {error}", exc_info=True)

        # Métriques
        self._failure_count += 1
        self.metrics.record_increment(
            "protocol_error",
            1,
            {
                "protocol": self.name,
                "chain": self.chain,
                "error_type": type(error).__name__,
            },
        )

        # Alerte
        await self._send_alert({
            "type": "error",
            "protocol": self.name,
            "chain": self.chain,
            "error": str(error),
            "timestamp": datetime.now().isoformat(),
        })

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
            "protocol": self.name,
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
    # MÉTHODES DE CALCUL
    # ============================================================

    def calculate_apy(self, rate: Decimal, compounding_frequency: int = 365) -> Decimal:
        """
        Calcule l'APY à partir d'un taux

        Args:
            rate: Taux d'intérêt
            compounding_frequency: Fréquence de composition

        Returns:
            APY
        """
        # APY = (1 + r/n)^n - 1
        r = float(rate)
        n = compounding_frequency
        apy = (Decimal(1) + Decimal(r) / n) ** n - Decimal(1)
        return apy

    def calculate_health_factor(
        self,
        collateral: Decimal,
        debt: Decimal,
        liquidation_threshold: Decimal,
    ) -> Decimal:
        """
        Calcule le health factor

        Args:
            collateral: Collatéral
            debt: Dette
            liquidation_threshold: Seuil de liquidation

        Returns:
            Health factor
        """
        if debt == 0:
            return Decimal("infinity")

        # HF = (collateral * liquidation_threshold) / debt
        health_factor = (collateral * liquidation_threshold) / debt
        return health_factor

    def calculate_risk_score(
        self,
        health_factor: Decimal,
        volatility: Decimal,
        liquidity: Decimal,
    ) -> float:
        """
        Calcule un score de risque

        Args:
            health_factor: Health factor
            volatility: Volatilité du token
            liquidity: Liquidité

        Returns:
            Score de risque (0-1)
        """
        # Score basé sur le health factor
        if health_factor > Decimal("2"):
            hf_score = 0.0
        elif health_factor > Decimal("1.5"):
            hf_score = 0.2
        elif health_factor > Decimal("1.2"):
            hf_score = 0.5
        elif health_factor > Decimal("1.05"):
            hf_score = 0.8
        else:
            hf_score = 1.0

        # Score basé sur la volatilité
        vol_score = min(1.0, float(volatility) / 100)

        # Score basé sur la liquidité
        liq_score = 1.0 - min(1.0, float(liquidity))

        # Score combiné
        score = (hf_score * 0.5 + vol_score * 0.3 + liq_score * 0.2)
        return min(1.0, score)

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques du protocole

        Returns:
            Statistiques
        """
        total_operations = self._operation_count
        success_rate = self._success_count / max(1, total_operations)

        return {
            "name": self.name,
            "protocol_type": self.protocol_type.value,
            "chain": self.chain,
            "status": self.status.value,
            "enabled": self.enabled,
            "total_operations": total_operations,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "active_positions": len(self._positions),
            "active_operations": len(self._active_operations),
            "total_value_locked": str(self._total_value_locked),
            "history_size": len(self._operation_history),
        }

    def get_config(self) -> Dict[str, Any]:
        """
        Obtient la configuration du protocole

        Returns:
            Configuration
        """
        return {
            "name": self.name,
            "protocol_type": self.protocol_type.value,
            "chain": self.chain,
            "status": self.status.value,
            "enabled": self.enabled,
            "supported_tokens": self.config.get("supported_tokens", []),
            "min_amount": str(self.config.get("min_amount", "0.001")),
            "max_amount": str(self.config.get("max_amount", "1000000")),
            "risk_level": self.config.get("risk_level", "medium"),
        }

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    def add_alert_callback(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les alertes

        Args:
            callback: Fonction callback
        """
        self._alert_callbacks.append(callback)

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """
        Envoie une alerte

        Args:
            alert: Données de l'alerte
        """
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

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
            "WETH": 18,
            "USDC": 6,
            "USDT": 6,
            "DAI": 18,
            "WBTC": 8,
            "MATIC": 18,
            "SOL": 9,
            "AVAX": 18,
            "BNB": 18,
            "LINK": 18,
            "AAVE": 18,
            "UNI": 18,
            "CRV": 18,
            "MKR": 18,
            "COMP": 18,
            "SNX": 18,
        }
        return decimals_map.get(token.upper(), 18)

    def _format_amount(self, amount: Decimal, decimals: int) -> int:
        """Formate un montant en wei"""
        return int(amount * Decimal(10 ** decimals))

    def _unformat_amount(self, amount: int, decimals: int) -> Decimal:
        """Déformate un montant depuis wei"""
        return Decimal(str(amount)) / Decimal(10 ** decimals)

    async def _sleep(self, seconds: float) -> None:
        """Attend le nombre de secondes spécifié"""
        await asyncio.sleep(seconds)

    def _get_risk_level(self, score: float) -> RiskLevel:
        """Obtient le niveau de risque à partir d'un score"""
        if score < 0.2:
            return RiskLevel.VERY_LOW
        elif score < 0.4:
            return RiskLevel.LOW
        elif score < 0.6:
            return RiskLevel.MEDIUM
        elif score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """
        Nettoie les ressources

        Cette méthode doit être appelée lors de l'arrêt du protocole
        """
        logger.info(f"Nettoyage du protocole {self.name}")

        # Nettoyage des opérations actives
        for operation_id in list(self._active_operations.keys()):
            try:
                # Annulation des opérations en cours
                self._active_operations[operation_id]["status"] = "cancelled"
            except Exception as e:
                logger.warning(f"Erreur d'annulation de {operation_id}: {e}")

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info(f"Protocole {self.name} nettoyé")

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
                    details={"action": "start"},
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
                    f"protocol_{func.__name__}_time",
                    elapsed,
                    {"protocol": self.name, "chain": self.chain},
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.debug(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
                raise

        return wrapper
    return decorator


def validate_token(token_key: str):
    """
    Décorateur pour valider un token

    Args:
        token_key: Nom du paramètre token
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Récupération du token
            token = kwargs.get(token_key)
            if token is None:
                # Recherche dans les args
                arg_names = func.__code__.co_varnames
                if token_key in arg_names:
                    idx = arg_names.index(token_key)
                    if idx < len(args):
                        token = args[idx]

            if not token:
                raise ValidationError("Token non spécifié")

            # Vérification du support
            supported_tokens = self.config.get("supported_tokens", [])
            if token not in supported_tokens:
                raise ValidationError(f"Token {token} non supporté par {self.name}")

            return await func(self, *args, **kwargs)

        return wrapper
    return decorator


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de la classe de base"""
    # Configuration
    config = {
        "name": "ExampleProtocol",
        "protocol_type": "lending",
        "chain": "ethereum",
        "contract_address": "0x...",
        "status": "active",
        "supported_tokens": ["ETH", "USDC", "USDT"],
        "min_amount": "0.001",
        "max_amount": "1000000",
        "risk_level": "medium",
        "enabled": True,
        "max_retries": 3,
        "retry_delay": 1.0,
        "max_workers": 10,
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création d'une implémentation de test
    class TestProtocol(BaseProtocol):
        async def get_positions(self, address):
            return []

        async def get_yield_data(self, token):
            return YieldData(
                protocol=self.name,
                chain=self.chain,
                token=token,
                apy=Decimal("0.05"),
                apr=Decimal("0.048"),
                rewards=[],
                risk_level=RiskLevel.MEDIUM,
                timestamp=datetime.now(),
            )

        async def get_protocol_health(self):
            return {
                "status": "healthy",
                "total_value_locked": "1000000",
                "active_users": 100,
            }

        async def execute_action(self, action, token, amount, address, **kwargs):
            return f"0x{hash(action + token + str(amount)):064x}"

    # Utilisation
    protocol = TestProtocol(config, wallet_manager)

    # Ajout d'un callback d'alerte
    def alert_callback(alert):
        print(f"ALERTE: {alert}")

    protocol.add_alert_callback(alert_callback)

    # Validation d'une action
    await protocol.validate_action(
        action="supply",
        token="USDC",
        amount=Decimal("1000"),
        address="0x1234567890123456789012345678901234567890",
    )

    # Obtention des données de rendement
    yield_data = await protocol.get_yield_data("USDC")
    print(f"Yield data: {yield_data.to_dict()}")

    # Exécution d'une action
    tx_hash = await protocol.execute_action(
        action="supply",
        token="USDC",
        amount=Decimal("1000"),
        address="0x1234567890123456789012345678901234567890",
    )
    print(f"Transaction: {tx_hash}")

    # Statistiques
    stats = protocol.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await protocol.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

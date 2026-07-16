# blockchain/bridges/bridge_manager.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Gestionnaire de Bridges

Ce module implémente un gestionnaire centralisé pour tous les bridges cross-chain,
offrant une interface unifiée pour les opérations de bridge, la gestion des
protocoles, le routage intelligent, et la coordination des transactions.

Fonctionnalités principales:
- Gestion unifiée de tous les protocoles de bridge
- Routage intelligent des transactions
- Agrégation des liquidités multi-protocoles
- Optimisation des coûts et des délais
- Gestion des pannes et fallback
- Monitoring centralisé
- Configuration dynamique
- Cache des routes et des devis
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
from collections import defaultdict, deque
from functools import lru_cache, wraps

import aiohttp

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_validator import BridgeValidator
    from .bridge_monitor import BridgeMonitor
    from .bridge_security import BridgeSecurityManager
    from .bridge_transaction import BridgeTransactionManager
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_validator import BridgeValidator
    from .bridge_monitor import BridgeMonitor
    from .bridge_security import BridgeSecurityManager
    from .bridge_transaction import BridgeTransactionManager
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class BridgeProtocol(Enum):
    """Protocoles de bridge supportés"""
    # Ethereum
    LAYERZERO = "layerzero"
    WORMHOLE = "wormhole"
    AXELAR = "axelar"
    CCTP = "cctp"
    ACROSS = "across"
    HOP = "hop"
    CONNEXT = "connext"
    SYNAPSE = "synapse"
    STARGATE = "stargate"
    DEBRIDGE = "debridge"
    
    # Optimism
    OPTIMISM_NATIVE = "optimism_native"
    
    # Polygon
    POLYGON_POS = "polygon_pos"
    POLYGON_PLASMA = "polygon_plasma"
    
    # Solana
    SOLANA_WORMHOLE = "solana_wormhole"
    SOLANA_DEBRIDGE = "solana_debridge"
    SOLANA_ALLBRIDGE = "solana_allbridge"
    
    # Generic
    GENERIC = "generic"


class BridgeStatus(Enum):
    """Statuts d'un bridge"""
    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class BridgeType(Enum):
    """Types de bridge"""
    LOCK_AND_MINT = "lock_and_mint"
    BURN_AND_MINT = "burn_and_mint"
    LOCK_AND_UNLOCK = "lock_and_unlock"
    SWAP = "swap"
    CCTP = "cctp"
    NATIVE = "native"


@dataclass
class BridgeConfig:
    """Configuration d'un bridge"""
    protocol: BridgeProtocol
    chain: str
    name: str
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

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol.value,
            "chain": self.chain,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "contract_address": self.contract_address,
            "supported_tokens": self.supported_tokens,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "gas_limit": self.gas_limit,
            "confirmations_required": self.confirmations_required,
            "enabled": self.enabled,
            "priority": self.priority,
        }


@dataclass
class BridgeRoute:
    """Route de bridge"""
    route_id: str
    protocol: BridgeProtocol
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    estimated_fees: Decimal
    estimated_time: int  # secondes
    confidence: float
    steps: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "route_id": self.route_id,
            "protocol": self.protocol.value,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "estimated_fees": str(self.estimated_fees),
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
            "steps": self.steps,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeManager:
    """
    Gestionnaire centralisé des bridges cross-chain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Any],
        transaction_manager: BridgeTransactionManager,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de bridges

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            transaction_manager: Gestionnaire de transactions
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.transaction_manager = transaction_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._bridges: Dict[str, BridgeConfig] = {}
        self._bridge_instances: Dict[str, BaseBridge] = {}
        self._routes_cache: Dict[str, Tuple[float, List[BridgeRoute]]] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Sous-systèmes
        self.validator = None
        self.monitor = None
        self.security_manager = None

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des prix
        self._price_cache: Dict[str, Dict[str, Decimal]] = {}

        # Statistiques
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Initialisation
        self._load_bridge_configs()
        self._initialize_bridges()
        self._initialize_subsystems()

        logger.info(f"BridgeManager initialisé avec {len(self._bridges)} bridges")

    # ============================================================
    # MÉTHODES D'INITIALISATION
    # ============================================================

    def _load_bridge_configs(self) -> None:
        """Charge les configurations des bridges"""
        try:
            # Configuration par défaut
            default_configs = self._get_default_configs()

            # Fusion avec la configuration utilisateur
            user_configs = self.config.get("bridges", {})

            for protocol, config in default_configs.items():
                if protocol in user_configs:
                    config.update(user_configs[protocol])

                bridge_config = BridgeConfig(
                    protocol=protocol,
                    chain=config.get("chain", "ethereum"),
                    name=config.get("name", protocol.value),
                    type=config.get("type", BridgeType.LOCK_AND_MINT),
                    status=config.get("status", BridgeStatus.ACTIVE),
                    contract_address=config.get("contract_address", ""),
                    supported_tokens=config.get("supported_tokens", []),
                    min_amount=Decimal(str(config.get("min_amount", "0.001"))),
                    max_amount=Decimal(str(config.get("max_amount", "1000000"))),
                    gas_limit=config.get("gas_limit", 200000),
                    confirmations_required=config.get("confirmations_required", 12),
                    enabled=config.get("enabled", True),
                    priority=config.get("priority", 0),
                    metadata=config.get("metadata", {}),
                )

                self._bridges[protocol.value] = bridge_config

            logger.info(f"Configurations des bridges chargées: {len(self._bridges)}")

        except Exception as e:
            logger.error(f"Erreur de chargement des configurations: {e}")
            raise BridgeError(f"Erreur de chargement des configurations: {e}")

    def _get_default_configs(self) -> Dict[BridgeProtocol, Dict[str, Any]]:
        """Obtient les configurations par défaut"""
        return {
            BridgeProtocol.LAYERZERO: {
                "name": "LayerZero",
                "type": BridgeType.LOCK_AND_MINT,
                "chain": "ethereum",
                "supported_tokens": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
                "min_amount": "0.001",
                "max_amount": "100000",
                "gas_limit": 300000,
                "confirmations_required": 12,
                "priority": 10,
            },
            BridgeProtocol.WORMHOLE: {
                "name": "Wormhole",
                "type": BridgeType.LOCK_AND_MINT,
                "chain": "ethereum",
                "supported_tokens": ["ETH", "USDC", "USDT", "DAI", "WBTC", "SOL"],
                "min_amount": "0.001",
                "max_amount": "200000",
                "gas_limit": 250000,
                "confirmations_required": 12,
                "priority": 20,
            },
            BridgeProtocol.CCTP: {
                "name": "Circle CCTP",
                "type": BridgeType.CCTP,
                "chain": "ethereum",
                "supported_tokens": ["USDC"],
                "min_amount": "1",
                "max_amount": "100000",
                "gas_limit": 200000,
                "confirmations_required": 12,
                "priority": 30,
            },
            BridgeProtocol.OPTIMISM_NATIVE: {
                "name": "Optimism Native Bridge",
                "type": BridgeType.NATIVE,
                "chain": "optimism",
                "supported_tokens": ["ETH", "USDC", "USDT", "DAI"],
                "min_amount": "0.001",
                "max_amount": "100000",
                "gas_limit": 300000,
                "confirmations_required": 12,
                "priority": 40,
            },
            BridgeProtocol.POLYGON_POS: {
                "name": "Polygon PoS Bridge",
                "type": BridgeType.LOCK_AND_MINT,
                "chain": "polygon",
                "supported_tokens": ["ETH", "MATIC", "USDC", "USDT", "DAI"],
                "min_amount": "0.001",
                "max_amount": "100000",
                "gas_limit": 300000,
                "confirmations_required": 12,
                "priority": 50,
            },
            BridgeProtocol.SOLANA_WORMHOLE: {
                "name": "Solana Wormhole",
                "type": BridgeType.LOCK_AND_MINT,
                "chain": "solana",
                "supported_tokens": ["SOL", "USDC", "USDT", "WETH", "WBTC"],
                "min_amount": "0.001",
                "max_amount": "100000",
                "gas_limit": 200000,
                "confirmations_required": 32,
                "priority": 60,
            },
            BridgeProtocol.DEBRIDGE: {
                "name": "deBridge",
                "type": BridgeType.SWAP,
                "chain": "ethereum",
                "supported_tokens": ["ETH", "USDC", "USDT", "DAI"],
                "min_amount": "0.001",
                "max_amount": "50000",
                "gas_limit": 300000,
                "confirmations_required": 12,
                "priority": 70,
            },
            BridgeProtocol.AXELAR: {
                "name": "Axelar",
                "type": BridgeType.LOCK_AND_MINT,
                "chain": "ethereum",
                "supported_tokens": ["ETH", "USDC", "USDT", "DAI"],
                "min_amount": "0.001",
                "max_amount": "100000",
                "gas_limit": 350000,
                "confirmations_required": 12,
                "priority": 80,
            },
        }

    def _initialize_bridges(self) -> None:
        """Initialise les instances de bridges"""
        # Import dynamique des bridges
        try:
            from .ethereum_bridge import EthereumBridge
            from .optimism_bridge import OptimismBridge
            from .polygon_bridge import PolygonBridge
            from .solana_bridge import SolanaBridge
            
            # Initialisation selon la chaîne
            for bridge_config in self._bridges.values():
                if not bridge_config.enabled:
                    continue

                try:
                    if bridge_config.chain in ["ethereum", "arbitrum", "base"]:
                        bridge = EthereumBridge(
                            config=bridge_config.metadata,
                            wallet_manager=self.wallet_manager,
                            web3_provider=self.web3_providers.get(bridge_config.chain),
                            bridge_manager=self,
                            transaction_manager=self.transaction_manager,
                        )
                    elif bridge_config.chain == "optimism":
                        bridge = OptimismBridge(
                            config=bridge_config.metadata,
                            wallet_manager=self.wallet_manager,
                            web3_providers=self.web3_providers,
                            bridge_manager=self,
                            transaction_manager=self.transaction_manager,
                        )
                    elif bridge_config.chain == "polygon":
                        bridge = PolygonBridge(
                            config=bridge_config.metadata,
                            wallet_manager=self.wallet_manager,
                            web3_providers=self.web3_providers,
                            bridge_manager=self,
                            transaction_manager=self.transaction_manager,
                        )
                    elif bridge_config.chain == "solana":
                        bridge = SolanaBridge(
                            config=bridge_config.metadata,
                            wallet_manager=self.wallet_manager,
                            solana_client=self.web3_providers.get("solana"),
                            bridge_manager=self,
                            transaction_manager=self.transaction_manager,
                        )
                    else:
                        # Bridge générique
                        from .base_bridge import BaseBridge
                        bridge = BaseBridge(
                            config=bridge_config.metadata,
                            wallet_manager=self.wallet_manager,
                        )

                    self._bridge_instances[bridge_config.protocol.value] = bridge
                    self.circuit_breakers[bridge_config.protocol.value] = CircuitBreaker(
                        failure_threshold=3,
                        recovery_timeout=60.0,
                        half_open_attempts=2,
                    )

                    logger.info(f"Bridge {bridge_config.protocol.value} initialisé")

                except Exception as e:
                    logger.error(f"Erreur d'initialisation du bridge {bridge_config.protocol.value}: {e}")

        except ImportError as e:
            logger.warning(f"Modules de bridge non disponibles: {e}")

    def _initialize_subsystems(self) -> None:
        """Initialise les sous-systèmes"""
        try:
            # Validateur
            from .bridge_validator import BridgeValidator
            self.validator = BridgeValidator(
                config=self.config.get("validator", {}),
                web3_providers=self.web3_providers,
            )

            # Moniteur
            from .bridge_monitor import BridgeMonitor
            self.monitor = BridgeMonitor(
                config=self.config.get("monitor", {}),
                bridge_manager=self,
                web3_providers=self.web3_providers,
            )

            # Gestionnaire de sécurité
            from .bridge_security import BridgeSecurityManager
            self.security_manager = BridgeSecurityManager(
                config=self.config.get("security", {}),
                web3_providers=self.web3_providers,
                bridge_manager=self,
                validator=self.validator,
            )

            logger.info("Sous-systèmes initialisés")

        except Exception as e:
            logger.error(f"Erreur d'initialisation des sous-systèmes: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    async def get_bridge(self, protocol: str, chain: str) -> Optional[BaseBridge]:
        """
        Obtient une instance de bridge

        Args:
            protocol: Protocole
            chain: Chaîne

        Returns:
            Instance du bridge ou None
        """
        bridge_key = f"{protocol}:{chain}"
        return self._bridge_instances.get(bridge_key)

    async def get_bridge_config(self, protocol: str) -> Optional[BridgeConfig]:
        """
        Obtient la configuration d'un bridge

        Args:
            protocol: Protocole

        Returns:
            Configuration du bridge ou None
        """
        return self._bridges.get(protocol)

    async def get_all_bridges(self) -> List[BridgeConfig]:
        """
        Obtient toutes les configurations de bridges

        Returns:
            Liste des configurations
        """
        return list(self._bridges.values())

    async def get_active_bridges(self) -> List[BridgeConfig]:
        """
        Obtient les bridges actifs

        Returns:
            Liste des bridges actifs
        """
        return [
            config for config in self._bridges.values()
            if config.enabled and config.status == BridgeStatus.ACTIVE
        ]

    async def get_bridge_route(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        preferred_protocols: Optional[List[str]] = None,
    ) -> List[BridgeRoute]:
        """
        Obtient les routes de bridge disponibles

        Args:
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            amount: Montant
            preferred_protocols: Protocoles préférés

        Returns:
            Liste des routes
        """
        route_key = f"{chain_from}:{chain_to}:{token_from}:{token_to}:{amount}"

        # Vérification du cache
        if route_key in self._routes_cache:
            cached_time, routes = self._routes_cache[route_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Routes retournées du cache")
                return routes

        try:
            routes = []

            # Sélection des bridges applicables
            applicable_bridges = []
            for bridge_config in self._bridges.values():
                if not bridge_config.enabled:
                    continue

                # Vérification de la compatibilité
                if bridge_config.chain != chain_from:
                    continue

                if token_from not in bridge_config.supported_tokens:
                    continue

                applicable_bridges.append(bridge_config)

            # Tri par priorité
            applicable_bridges.sort(key=lambda x: x.priority)

            # Préférence des protocoles
            if preferred_protocols:
                applicable_bridges.sort(
                    key=lambda x: (
                        preferred_protocols.index(x.protocol.value)
                        if x.protocol.value in preferred_protocols
                        else 999
                    )
                )

            # Génération des routes pour chaque bridge
            for bridge_config in applicable_bridges:
                try:
                    route = await self._generate_route(
                        bridge_config,
                        chain_from,
                        chain_to,
                        token_from,
                        token_to,
                        amount,
                    )
                    if route:
                        routes.append(route)
                except Exception as e:
                    logger.warning(f"Erreur de génération de route pour {bridge_config.protocol.value}: {e}")

            # Mise en cache
            self._routes_cache[route_key] = (time.time(), routes)

            # Métriques
            self.metrics.record_gauge(
                "bridge_routes_found",
                len(routes),
                {
                    "chain_from": chain_from,
                    "chain_to": chain_to,
                    "token_from": token_from,
                    "token_to": token_to,
                },
            )

            return routes

        except Exception as e:
            logger.error(f"Erreur d'obtention des routes: {e}")
            raise BridgeError(f"Erreur d'obtention des routes: {e}")

    async def execute_bridge(
        self,
        route: BridgeRoute,
        source_address: str,
        destination_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge via une route

        Args:
            route: Route à exécuter
            source_address: Adresse source
            destination_address: Adresse destination
            **kwargs: Arguments additionnels

        Returns:
            Résultat de l'exécution
        """
        bridge_key = route.protocol.value
        operation_id = f"op_{uuid.uuid4().hex[:12]}"

        logger.info(f"Exécution du bridge {operation_id} via {bridge_key}")

        try:
            # Vérification du circuit breaker
            if bridge_key in self.circuit_breakers:
                if not self.circuit_breakers[bridge_key].is_available():
                    raise BridgeError(f"Circuit breaker ouvert pour {bridge_key}")

            # Récupération de l'instance du bridge
            bridge = await self.get_bridge(bridge_key, route.chain_from)
            if not bridge:
                raise BridgeError(f"Bridge {bridge_key} non trouvé")

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(source_address)
            if not wallet:
                raise BridgeError(f"Wallet non trouvé: {source_address}")

            # Enregistrement de l'opération
            self._active_operations[operation_id] = {
                "route": route,
                "source_address": source_address,
                "destination_address": destination_address,
                "start_time": datetime.now(),
                "status": "pending",
            }

            # Validation de la transaction
            if self.validator:
                validation_result = await self.validator.validate_bridge(
                    route=route,
                    source_address=source_address,
                    destination_address=destination_address,
                )
                if not validation_result.is_valid():
                    raise ValidationError(
                        f"Validation échouée: {validation_result.message}"
                    )

            # Exécution du bridge
            # Note: La méthode exacte dépend du type de bridge
            result = await bridge.execute(
                route=route,
                source_address=source_address,
                destination_address=destination_address,
                **kwargs,
            )

            # Mise à jour du statut
            self._active_operations[operation_id]["status"] = "completed"
            self._active_operations[operation_id]["result"] = result

            # Métriques
            self.metrics.record_increment(
                "bridge_execution_success",
                {
                    "protocol": bridge_key,
                    "chain_from": route.chain_from,
                    "chain_to": route.chain_to,
                    "token_from": route.token_from,
                    "token_to": route.token_to,
                },
            )

            return result

        except Exception as e:
            logger.error(f"Erreur d'exécution du bridge {operation_id}: {e}")

            # Mise à jour du statut
            if operation_id in self._active_operations:
                self._active_operations[operation_id]["status"] = "failed"
                self._active_operations[operation_id]["error"] = str(e)

            # Enregistrement de l'échec dans le circuit breaker
            if bridge_key in self.circuit_breakers:
                self.circuit_breakers[bridge_key].record_failure()

            self.metrics.record_increment(
                "bridge_execution_failure",
                {
                    "protocol": bridge_key,
                    "error": str(e)[:50],
                },
            )

            raise BridgeError(f"Erreur d'exécution du bridge: {e}")

        finally:
            # Nettoyage après un certain temps
            await asyncio.sleep(3600)  # 1 heure
            self._active_operations.pop(operation_id, None)

    async def pause_bridge(self, protocol: str, chain: str) -> bool:
        """
        Met en pause un bridge

        Args:
            protocol: Protocole
            chain: Chaîne

        Returns:
            True si mis en pause avec succès
        """
        bridge_config = await self.get_bridge_config(protocol)
        if not bridge_config:
            return False

        bridge_config.status = BridgeStatus.PAUSED
        bridge_config.enabled = False

        logger.info(f"Bridge {protocol} mis en pause")
        return True

    async def resume_bridge(self, protocol: str, chain: str) -> bool:
        """
        Reprend un bridge en pause

        Args:
            protocol: Protocole
            chain: Chaîne

        Returns:
            True si repris avec succès
        """
        bridge_config = await self.get_bridge_config(protocol)
        if not bridge_config:
            return False

        bridge_config.status = BridgeStatus.ACTIVE
        bridge_config.enabled = True

        logger.info(f"Bridge {protocol} repris")
        return True

    async def get_bridge_status(self, protocol: str, chain: str) -> Optional[BridgeStatus]:
        """
        Obtient le statut d'un bridge

        Args:
            protocol: Protocole
            chain: Chaîne

        Returns:
            Statut du bridge
        """
        bridge_config = await self.get_bridge_config(protocol)
        if not bridge_config:
            return None

        return bridge_config.status

    # ============================================================
    # MÉTHODES DE GÉNÉRATION DE ROUTES
    # ============================================================

    async def _generate_route(
        self,
        bridge_config: BridgeConfig,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
    ) -> Optional[BridgeRoute]:
        """Génère une route pour un bridge spécifique"""
        try:
            # Vérification des limites
            if amount < bridge_config.min_amount:
                return None

            if amount > bridge_config.max_amount:
                return None

            # Calcul des frais estimés
            fees = await self._estimate_fees(
                bridge_config,
                chain_from,
                chain_to,
                token_from,
                token_to,
                amount,
            )

            # Calcul du temps estimé
            estimated_time = await self._estimate_time(
                bridge_config,
                chain_from,
                chain_to,
            )

            # Niveau de confiance
            confidence = await self._calculate_confidence(
                bridge_config,
                amount,
            )

            # Construction de la route
            route = BridgeRoute(
                route_id=f"route_{uuid.uuid4().hex[:8]}",
                protocol=bridge_config.protocol,
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                estimated_fees=fees,
                estimated_time=estimated_time,
                confidence=confidence,
                steps=[
                    {
                        "action": "approve",
                        "contract": bridge_config.contract_address,
                        "amount": str(amount),
                    },
                    {
                        "action": "bridge",
                        "contract": bridge_config.contract_address,
                        "to": "destination",
                    },
                ],
                metadata={
                    "bridge_config": bridge_config.to_dict(),
                    "gas_limit": bridge_config.gas_limit,
                    "confirmations_required": bridge_config.confirmations_required,
                },
            )

            return route

        except Exception as e:
            logger.error(f"Erreur de génération de route: {e}")
            return None

    async def _estimate_fees(
        self,
        bridge_config: BridgeConfig,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
    ) -> Decimal:
        """Estime les frais d'un bridge"""
        # Estimation basée sur le type de bridge
        base_fee = amount * Decimal("0.001")  # 0.1% de base

        # Ajustement selon le protocole
        protocol_fee_multipliers = {
            BridgeProtocol.LAYERZERO: Decimal("1.2"),
            BridgeProtocol.WORMHOLE: Decimal("1.0"),
            BridgeProtocol.CCTP: Decimal("0.8"),
            BridgeProtocol.OPTIMISM_NATIVE: Decimal("0.9"),
            BridgeProtocol.POLYGON_POS: Decimal("0.9"),
            BridgeProtocol.SOLANA_WORMHOLE: Decimal("0.7"),
            BridgeProtocol.DEBRIDGE: Decimal("1.1"),
            BridgeProtocol.AXELAR: Decimal("1.3"),
        }

        multiplier = protocol_fee_multipliers.get(
            bridge_config.protocol,
            Decimal("1.0")
        )

        fees = base_fee * multiplier

        # Frais de gaz estimés
        gas_cost = await self._estimate_gas_cost(bridge_config, chain_from)

        fees += gas_cost

        return fees

    async def _estimate_gas_cost(
        self,
        bridge_config: BridgeConfig,
        chain: str,
    ) -> Decimal:
        """Estime le coût du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0.001")

            gas_price = await provider.eth.gas_price
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            gas_cost = Decimal(str(bridge_config.gas_limit)) * gas_price_decimal
            return gas_cost

        except Exception:
            return Decimal("0.001")

    async def _estimate_time(
        self,
        bridge_config: BridgeConfig,
        chain_from: str,
        chain_to: str,
    ) -> int:
        """Estime le temps de bridge"""
        # Temps de base par protocole
        base_time = {
            BridgeProtocol.LAYERZERO: 120,
            BridgeProtocol.WORMHOLE: 90,
            BridgeProtocol.CCTP: 60,
            BridgeProtocol.OPTIMISM_NATIVE: 120,
            BridgeProtocol.POLYGON_POS: 120,
            BridgeProtocol.SOLANA_WORMHOLE: 30,
            BridgeProtocol.DEBRIDGE: 150,
            BridgeProtocol.AXELAR: 180,
        }.get(bridge_config.protocol, 120)

        # Ajustement selon les chaînes
        slow_chains = {"ethereum", "solana"}
        if chain_from in slow_chains or chain_to in slow_chains:
            base_time = int(base_time * 1.5)

        return base_time

    async def _calculate_confidence(
        self,
        bridge_config: BridgeConfig,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = 0.95

        # Ajustement selon le statut du bridge
        if bridge_config.status != BridgeStatus.ACTIVE:
            base_confidence -= 0.2

        # Ajustement selon le montant
        if amount > bridge_config.max_amount * Decimal("0.8"):
            base_confidence -= 0.1

        # Ajustement selon le circuit breaker
        if bridge_config.protocol.value in self.circuit_breakers:
            cb = self.circuit_breakers[bridge_config.protocol.value]
            if cb.failure_count > 0:
                base_confidence -= min(0.2, cb.failure_count * 0.02)

        return max(0.5, min(0.99, base_confidence))

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring des bridges"""
        if self.monitor:
            await self.monitor.start_monitoring()

        if self.security_manager:
            await self.security_manager.start_monitoring()

        logger.info("Monitoring des bridges démarré")

    async def stop_monitoring(self) -> None:
        """Arrête le monitoring des bridges"""
        if self.monitor:
            await self.monitor.stop_monitoring()

        if self.security_manager:
            await self.security_manager.stop_monitoring()

        logger.info("Monitoring des bridges arrêté")

    async def get_health(self) -> Dict[str, Any]:
        """Obtient l'état de santé de tous les bridges"""
        health = {}

        for bridge_config in self._bridges.values():
            try:
                if bridge_config.enabled:
                    status = await self.get_bridge_status(
                        bridge_config.protocol.value,
                        bridge_config.chain,
                    )

                    health[bridge_config.protocol.value] = {
                        "status": status.value if status else "unknown",
                        "chain": bridge_config.chain,
                        "enabled": bridge_config.enabled,
                        "priority": bridge_config.priority,
                    }
            except Exception as e:
                health[bridge_config.protocol.value] = {
                    "status": "error",
                    "error": str(e),
                }

        return health

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        return {
            "total_bridges": len(self._bridges),
            "active_bridges": len([b for b in self._bridges.values() if b.enabled]),
            "active_operations": len(self._active_operations),
            "cached_routes": len(self._routes_cache),
            "circuit_breakers": {
                name: {
                    "available": cb.is_available(),
                    "failure_count": cb.failure_count,
                    "success_count": cb.success_count,
                }
                for name, cb in self.circuit_breakers.items()
            },
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeManager...")

        await self.stop_monitoring()

        # Nettoyage des instances
        for bridge in self._bridge_instances.values():
            try:
                await bridge.cleanup()
            except Exception as e:
                logger.warning(f"Erreur de nettoyage du bridge: {e}")

        self._bridge_instances.clear()
        self._routes_cache.clear()
        self._active_operations.clear()

        if self.validator:
            await self.validator.cleanup()

        if self.monitor:
            await self.monitor.cleanup()

        if self.security_manager:
            await self.security_manager.cleanup()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Any],
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> BridgeManager:
    """
    Crée une instance de BridgeManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeManager
    """
    return BridgeManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        transaction_manager=transaction_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeManager"""
    # Configuration
    config = {
        "bridges": {
            "wormhole": {
                "enabled": True,
                "priority": 10,
                "contract_address": "0x...",
            },
            "layerzero": {
                "enabled": True,
                "priority": 20,
                "contract_address": "0x...",
            },
        },
        "validator": {
            "validation_rules": {
                "require_signature": True,
                "min_confirmations": 12,
            },
        },
        "monitor": {
            "monitored_protocols": ["wormhole", "layerzero"],
            "monitored_chains": ["ethereum", "polygon"],
        },
        "security": {
            "suspicious_addresses": {
                "ethereum": ["0x..."],
            },
        },
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Wallet manager
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Transaction manager
    class SimpleTransactionManager:
        pass

    transaction_manager = SimpleTransactionManager()

    # Création du gestionnaire de bridges
    bridge_manager = create_bridge_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        transaction_manager=transaction_manager,
    )

    # Démarrage du monitoring
    await bridge_manager.start_monitoring()

    # Obtention des routes
    routes = await bridge_manager.get_bridge_route(
        chain_from="ethereum",
        chain_to="polygon",
        token_from="USDC",
        token_to="USDC",
        amount=Decimal("1000"),
    )

    print(f"Routes trouvées: {len(routes)}")
    for route in routes:
        print(f"  - {route.protocol.value}: {route.estimated_fees} fees")

    # Exécution d'un bridge
    if routes:
        route = routes[0]  # Prendre la meilleure route
        result = await bridge_manager.execute_bridge(
            route=route,
            source_address="0x...",
            destination_address="0x...",
        )
        print(f"Résultat: {result}")

    # Statistiques
    stats = bridge_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await bridge_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

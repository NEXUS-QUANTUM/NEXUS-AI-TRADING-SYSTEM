# blockchain/bridges/bridge_events.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Gestion des Événements de Bridge

Ce module implémente un système complet de gestion des événements pour les
opérations de bridge cross-chain, incluant l'écoute, le traitement, le stockage
et l'analyse des événements on-chain et off-chain.

Fonctionnalités principales:
- Écoute des événements on-chain (logs)
- Traitement des événements de bridge
- Stockage et indexation des événements
- Analyse des patterns d'événements
- Alertes en temps réel
- Replay des événements historiques
- Support des événements multi-protocoles
- Filtrage et recherche avancée
- Agrégation des événements
- Webhooks pour les événements
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
import web3
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, EventError, ValidationError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, EventError, ValidationError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class EventType(Enum):
    """Types d'événements"""
    # Bridge events
    BRIDGE_INITIATED = "bridge_initiated"
    BRIDGE_COMPLETED = "bridge_completed"
    BRIDGE_FAILED = "bridge_failed"
    BRIDGE_CANCELLED = "bridge_cancelled"
    
    # Deposit events
    DEPOSIT_STARTED = "deposit_started"
    DEPOSIT_CONFIRMED = "deposit_confirmed"
    DEPOSIT_FAILED = "deposit_failed"
    
    # Withdrawal events
    WITHDRAWAL_STARTED = "withdrawal_started"
    WITHDRAWAL_CONFIRMED = "withdrawal_confirmed"
    WITHDRAWAL_FAILED = "withdrawal_failed"
    
    # Token events
    TOKEN_APPROVED = "token_approved"
    TOKEN_TRANSFERRED = "token_transferred"
    TOKEN_RECEIVED = "token_received"
    TOKEN_BURNED = "token_burned"
    TOKEN_MINTED = "token_minted"
    
    # Security events
    SECURITY_ALERT = "security_alert"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    VALIDATOR_EVENT = "validator_event"
    
    # System events
    SYSTEM_STATUS_CHANGED = "system_status_changed"
    CONFIG_UPDATED = "config_updated"
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    SERVICE_ERROR = "service_error"


class EventSource(Enum):
    """Sources d'événements"""
    ON_CHAIN = "on_chain"
    OFF_CHAIN = "off_chain"
    SYSTEM = "system"
    USER = "user"
    VALIDATOR = "validator"
    RELAYER = "relayer"


class EventStatus(Enum):
    """Statuts d'événement"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


@dataclass
class BridgeEvent:
    """Événement de bridge"""
    event_id: str
    event_type: EventType
    source: EventSource
    protocol: str
    chain: str
    status: EventStatus
    timestamp: datetime
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    block_hash: Optional[str] = None
    bridge_id: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    token: Optional[str] = None
    amount: Optional[Decimal] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "protocol": self.protocol,
            "chain": self.chain,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "bridge_id": self.bridge_id,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "token": self.token,
            "amount": str(self.amount) if self.amount else None,
            "data": self.data,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "error_message": self.error_message,
        }

    def is_relevant(self) -> bool:
        """Vérifie si l'événement est pertinent"""
        return self.status not in [EventStatus.IGNORED, EventStatus.FAILED]


@dataclass
class EventSubscription:
    """Abonnement à des événements"""
    subscription_id: str
    event_types: List[EventType]
    protocols: Optional[List[str]] = None
    chains: Optional[List[str]] = None
    addresses: Optional[List[str]] = None
    callback: Optional[Callable] = None
    webhook_url: Optional[str] = None
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "subscription_id": self.subscription_id,
            "event_types": [e.value for e in self.event_types],
            "protocols": self.protocols,
            "chains": self.chains,
            "addresses": self.addresses,
            "webhook_url": self.webhook_url,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EventFilter:
    """Filtre d'événements"""
    event_types: Optional[List[EventType]] = None
    protocols: Optional[List[str]] = None
    chains: Optional[List[str]] = None
    addresses: Optional[List[str]] = None
    tokens: Optional[List[str]] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    statuses: Optional[List[EventStatus]] = None
    bridge_ids: Optional[List[str]] = None
    tx_hashes: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "event_types": [e.value for e in self.event_types] if self.event_types else None,
            "protocols": self.protocols,
            "chains": self.chains,
            "addresses": self.addresses,
            "tokens": self.tokens,
            "from_date": self.from_date.isoformat() if self.from_date else None,
            "to_date": self.to_date.isoformat() if self.to_date else None,
            "min_amount": str(self.min_amount) if self.min_amount else None,
            "max_amount": str(self.max_amount) if self.max_amount else None,
            "statuses": [s.value for s in self.statuses] if self.statuses else None,
            "bridge_ids": self.bridge_ids,
            "tx_hashes": self.tx_hashes,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeEventManager:
    """
    Gestionnaire d'événements pour les bridges cross-chain
    """

    # Signatures d'événements courantes
    EVENT_SIGNATURES = {
        "Transfer(address,address,uint256)": EventType.TOKEN_TRANSFERRED,
        "Approval(address,address,uint256)": EventType.TOKEN_APPROVED,
        "Deposit(address,address,uint256,address)": EventType.DEPOSIT_STARTED,
        "Withdrawal(address,address,uint256,address)": EventType.WITHDRAWAL_STARTED,
        "Bridge(address,address,uint256,bytes32)": EventType.BRIDGE_INITIATED,
        "BridgeCompleted(bytes32,address,uint256)": EventType.BRIDGE_COMPLETED,
        "BridgeFailed(bytes32,string)": EventType.BRIDGE_FAILED,
        "ValidatorEvent(address,uint256,bool)": EventType.VALIDATOR_EVENT,
        "SecurityAlert(address,string,uint256)": EventType.SECURITY_ALERT,
    }

    # Signatures d'événements spécifiques aux protocoles
    PROTOCOL_SIGNATURES = {
        "layerzero": {
            "MessageSent(bytes32,uint16,bytes)": EventType.BRIDGE_INITIATED,
            "MessageReceived(bytes32,address,bytes)": EventType.BRIDGE_COMPLETED,
        },
        "wormhole": {
            "Transfer(address,address,uint256)": EventType.TOKEN_TRANSFERRED,
            "MessagePublished(address,uint64,bytes)": EventType.BRIDGE_INITIATED,
        },
        "cctp": {
            "DepositForBurn(uint64,address,uint256,address)": EventType.DEPOSIT_STARTED,
            "MintAndWithdraw(uint64,address,uint256,address)": EventType.WITHDRAWAL_CONFIRMED,
        },
    }

    def __init__(
        self,
        config: Dict[str, Any],
        bridge_manager: BridgeManager,
        web3_providers: Dict[str, Web3],
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire d'événements

        Args:
            config: Configuration
            bridge_manager: Gestionnaire de bridges
            web3_providers: Providers Web3 par chaîne
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.bridge_manager = bridge_manager
        self.web3_providers = web3_providers
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._events: List[BridgeEvent] = []
        self._event_index: Dict[str, BridgeEvent] = {}
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._event_queue: deque = deque(maxlen=10000)
        self._processed_events: Set[str] = set()
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Caches
        self._event_cache: Dict[str, Tuple[float, BridgeEvent]] = {}
        self._contract_cache: Dict[str, Dict[str, Contract]] = {}

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # États de monitoring
        self._is_running = False
        self._monitor_tasks: List[asyncio.Task] = []
        self._last_processed_block: Dict[str, int] = {}

        # Statistiques
        self._event_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Charge les configurations
        self._load_config()
        self._initialize_contracts()

        logger.info("BridgeEventManager initialisé avec succès")

    def _load_config(self) -> None:
        """Charge la configuration"""
        self._start_block = self.config.get("start_block", 0)
        self._max_events_per_batch = self.config.get("max_events_per_batch", 1000)
        self._poll_interval = self.config.get("poll_interval", 2)
        self._enabled_protocols = self.config.get("enabled_protocols", [])
        self._enabled_chains = self.config.get("enabled_chains", [])

    def _initialize_contracts(self) -> None:
        """Initialise les contrats pour l'écoute des événements"""
        try:
            for chain, provider in self.web3_providers.items():
                self._contract_cache[chain] = {}
                # Récupération des adresses de contrats depuis le bridge manager
                bridge_configs = asyncio.run(
                    self.bridge_manager.get_all_bridges()
                )
                for config in bridge_configs:
                    if config.chain == chain and config.contract_address:
                        contract = provider.eth.contract(
                            address=to_checksum_address(config.contract_address),
                            abi=self._get_contract_abi(config.protocol.value),
                        )
                        self._contract_cache[chain][config.protocol.value] = contract

            logger.info(f"Contrats initialisés: {len(self._contract_cache)} chaînes")

        except Exception as e:
            logger.error(f"Erreur d'initialisation des contrats: {e}")

    def _get_contract_abi(self, protocol: str) -> List[Dict[str, Any]]:
        """Obtient l'ABI pour un protocole spécifique"""
        # ABI de base pour les événements
        base_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "from", "type": "address"},
                    {"indexed": True, "name": "to", "type": "address"},
                    {"indexed": False, "name": "value", "type": "uint256"},
                ],
                "name": "Transfer",
                "type": "event",
            },
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "owner", "type": "address"},
                    {"indexed": True, "name": "spender", "type": "address"},
                    {"indexed": False, "name": "value", "type": "uint256"},
                ],
                "name": "Approval",
                "type": "event",
            },
        ]

        # ABI spécifique au protocole
        protocol_abis = {
            "layerzero": [
                {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "srcChainId", "type": "uint16"},
                        {"indexed": False, "name": "srcAddress", "type": "bytes"},
                        {"indexed": False, "name": "nonce", "type": "uint64"},
                        {"indexed": False, "name": "payload", "type": "bytes"},
                    ],
                    "name": "MessageReceived",
                    "type": "event",
                },
            ],
            "wormhole": [
                {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "emitterChainId", "type": "uint16"},
                        {"indexed": True, "name": "emitterAddress", "type": "bytes32"},
                        {"indexed": False, "name": "sequence", "type": "uint64"},
                        {"indexed": False, "name": "payload", "type": "bytes"},
                    ],
                    "name": "MessagePublished",
                    "type": "event",
                },
            ],
        }

        base_abi.extend(protocol_abis.get(protocol, []))
        return base_abi

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    async def start_listening(self) -> None:
        """Démarre l'écoute des événements"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage de l'écoute des événements")

        # Tâches d'écoute
        for chain in self.web3_providers.keys():
            if self._enabled_chains and chain not in self._enabled_chains:
                continue

            task = asyncio.create_task(self._listen_events(chain))
            self._monitor_tasks.append(task)

        # Tâche de traitement
        self._monitor_tasks.append(
            asyncio.create_task(self._process_event_queue())
        )

        # Tâche de nettoyage
        self._monitor_tasks.append(
            asyncio.create_task(self._cleanup_events())
        )

    async def stop_listening(self) -> None:
        """Arrête l'écoute des événements"""
        self._is_running = False

        for task in self._monitor_tasks:
            task.cancel()

        try:
            await asyncio.gather(*self._monitor_tasks, return_exceptions=True)
        except Exception:
            pass

        self._monitor_tasks.clear()
        logger.info("Écoute des événements arrêtée")

    async def get_events(
        self,
        filter_params: Optional[EventFilter] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BridgeEvent]:
        """
        Obtient les événements filtrés

        Args:
            filter_params: Paramètres de filtrage
            limit: Nombre maximum d'événements
            offset: Décalage

        Returns:
            Liste des événements
        """
        events = self._events.copy()

        if filter_params:
            events = await self._apply_filter(events, filter_params)

        # Tri par date (plus récent en premier)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[offset:offset + limit]

    async def get_event_by_id(self, event_id: str) -> Optional[BridgeEvent]:
        """
        Obtient un événement par son ID

        Args:
            event_id: ID de l'événement

        Returns:
            Événement ou None
        """
        return self._event_index.get(event_id)

    async def get_events_by_bridge(self, bridge_id: str) -> List[BridgeEvent]:
        """
        Obtient les événements associés à un bridge

        Args:
            bridge_id: ID du bridge

        Returns:
            Liste des événements
        """
        return [
            event for event in self._events
            if event.bridge_id == bridge_id
        ]

    async def get_events_by_transaction(self, tx_hash: str) -> List[BridgeEvent]:
        """
        Obtient les événements associés à une transaction

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Liste des événements
        """
        return [
            event for event in self._events
            if event.tx_hash == tx_hash
        ]

    async def get_event_stats(self) -> Dict[str, Any]:
        """
        Obtient les statistiques des événements

        Returns:
            Statistiques
        """
        total_events = len(self._events)
        processed_events = len(self._processed_events)

        # Statistiques par type
        event_types = defaultdict(int)
        for event in self._events:
            event_types[event.event_type.value] += 1

        # Statistiques par protocole
        protocols = defaultdict(int)
        for event in self._events:
            protocols[event.protocol] += 1

        # Statistiques par chaîne
        chains = defaultdict(int)
        for event in self._events:
            chains[event.chain] += 1

        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "event_types": dict(event_types),
            "protocols": dict(protocols),
            "chains": dict(chains),
            "queue_size": len(self._event_queue),
            "subscriptions": len(self._subscriptions),
            "listeners": sum(len(v) for v in self._listeners.values()),
        }

    # ============================================================
    # MÉTHODES D'ABONNEMENT
    # ============================================================

    async def subscribe(
        self,
        event_types: List[EventType],
        protocols: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        addresses: Optional[List[str]] = None,
        callback: Optional[Callable] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EventSubscription:
        """
        Crée un abonnement à des événements

        Args:
            event_types: Types d'événements
            protocols: Protocoles concernés
            chains: Chaînes concernées
            addresses: Adresses concernées
            callback: Fonction callback
            webhook_url: URL du webhook
            metadata: Métadonnées

        Returns:
            Abonnement créé
        """
        subscription_id = f"sub_{uuid.uuid4().hex[:12]}"

        subscription = EventSubscription(
            subscription_id=subscription_id,
            event_types=event_types,
            protocols=protocols,
            chains=chains,
            addresses=addresses,
            callback=callback,
            webhook_url=webhook_url,
            metadata=metadata or {},
        )

        self._subscriptions[subscription_id] = subscription

        if callback:
            self._listeners[subscription_id].append(callback)

        logger.info(f"Abonnement créé: {subscription_id}")
        return subscription

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Supprime un abonnement

        Args:
            subscription_id: ID de l'abonnement

        Returns:
            True si supprimé avec succès
        """
        if subscription_id not in self._subscriptions:
            return False

        self._subscriptions.pop(subscription_id, None)
        self._listeners.pop(subscription_id, None)

        logger.info(f"Abonnement supprimé: {subscription_id}")
        return True

    async def add_event_listener(
        self,
        event_type: EventType,
        callback: Callable,
        protocol: Optional[str] = None,
        chain: Optional[str] = None,
    ) -> str:
        """
        Ajoute un écouteur d'événements

        Args:
            event_type: Type d'événement
            callback: Fonction callback
            protocol: Protocole (optionnel)
            chain: Chaîne (optionnel)

        Returns:
            ID de l'écouteur
        """
        listener_id = f"lst_{uuid.uuid4().hex[:12]}"
        key = f"{event_type.value}:{protocol or 'all'}:{chain or 'all'}"

        self._listeners[key].append(callback)

        logger.info(f"Écouteur ajouté: {listener_id}")
        return listener_id

    async def remove_event_listener(self, listener_id: str) -> bool:
        """
        Supprime un écouteur d'événements

        Args:
            listener_id: ID de l'écouteur

        Returns:
            True si supprimé avec succès
        """
        for key, listeners in self._listeners.items():
            for i, listener in enumerate(listeners):
                if hasattr(listener, '__name__') and listener.__name__ == listener_id:
                    self._listeners[key].pop(i)
                    return True
        return False

    # ============================================================
    # MÉTHODES D'ÉCOUTE
    # ============================================================

    async def _listen_events(self, chain: str) -> None:
        """Écoute les événements sur une chaîne"""
        provider = self.web3_providers.get(chain)
        if not provider:
            logger.error(f"Provider Web3 non trouvé pour {chain}")
            return

        # Ajout du middleware PoA pour les chaînes compatibles
        if chain in ["polygon", "bsc", "arbitrum", "optimism"]:
            try:
                provider.middleware_onion.inject(geth_poa_middleware, layer=0)
            except Exception:
                pass

        # Dernier bloc traité
        last_block = self._last_processed_block.get(chain, self._start_block)

        logger.info(f"Écoute des événements sur {chain} à partir du bloc {last_block}")

        while self._is_running:
            try:
                # Récupération du bloc actuel
                current_block = await provider.eth.block_number

                if last_block < current_block:
                    # Récupération des événements
                    events = await self._fetch_events(
                        provider=provider,
                        chain=chain,
                        from_block=last_block + 1,
                        to_block=current_block,
                    )

                    # Traitement des événements
                    for event in events:
                        await self._queue_event(event)

                    last_block = current_block
                    self._last_processed_block[chain] = last_block

                    # Métriques
                    if events:
                        self.metrics.record_increment(
                            "bridge_events_fetched",
                            len(events),
                            {"chain": chain},
                        )

                await asyncio.sleep(self._poll_interval)

            except Exception as e:
                logger.error(f"Erreur d'écoute des événements sur {chain}: {e}")
                await asyncio.sleep(10)

    async def _fetch_events(
        self,
        provider: Web3,
        chain: str,
        from_block: int,
        to_block: int,
    ) -> List[BridgeEvent]:
        """Récupère les événements d'un bloc"""
        events = []

        try:
            # Récupération des logs
            logs = await provider.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
            })

            # Traitement des logs
            for log in logs:
                try:
                    event = await self._parse_log(
                        chain=chain,
                        log=dict(log),
                        provider=provider,
                    )
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.debug(f"Erreur de parsing de log: {e}")

            return events

        except Exception as e:
            logger.error(f"Erreur de récupération des logs: {e}")
            return []

    async def _parse_log(
        self,
        chain: str,
        log: Dict[str, Any],
        provider: Web3,
    ) -> Optional[BridgeEvent]:
        """Parse un log en événement"""
        try:
            # Récupération de la signature
            topic = log.get("topics", [])[0] if log.get("topics") else None
            if not topic:
                return None

            topic_hex = topic.hex() if hasattr(topic, 'hex') else topic

            # Identification du type d'événement
            event_type = await self._identify_event_type(topic_hex)

            if not event_type:
                return None

            # Extraction des données
            data = log.get("data", "0x")
            address = log.get("address")

            # Récupération de la transaction
            tx_hash = log.get("transactionHash")
            if tx_hash and hasattr(tx_hash, 'hex'):
                tx_hash = tx_hash.hex()

            # Récupération du bloc
            block_number = log.get("blockNumber")
            block_hash = log.get("blockHash")

            # Decodage selon le type
            decoded_data = await self._decode_event_data(
                event_type=event_type,
                topics=log.get("topics", []),
                data=data,
                provider=provider,
            )

            # Création de l'événement
            event = BridgeEvent(
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                event_type=event_type,
                source=EventSource.ON_CHAIN,
                protocol=self._get_protocol_from_address(address, chain),
                chain=chain,
                status=EventStatus.PENDING,
                timestamp=datetime.now(),
                tx_hash=tx_hash,
                block_number=block_number,
                block_hash=block_hash.hex() if block_hash and hasattr(block_hash, 'hex') else None,
                from_address=decoded_data.get("from"),
                to_address=decoded_data.get("to"),
                token=decoded_data.get("token"),
                amount=decoded_data.get("amount"),
                data=decoded_data,
            )

            return event

        except Exception as e:
            logger.debug(f"Erreur de parsing de log: {e}")
            return None

    async def _identify_event_type(self, topic: str) -> Optional[EventType]:
        """Identifie le type d'événement à partir de la signature"""
        # Vérification dans les signatures standard
        for signature, event_type in self.EVENT_SIGNATURES.items():
            if Web3.keccak(text=signature).hex() == topic:
                return event_type

        # Vérification dans les signatures des protocoles
        for protocol, signatures in self.PROTOCOL_SIGNATURES.items():
            for signature, event_type in signatures.items():
                if Web3.keccak(text=signature).hex() == topic:
                    return event_type

        return None

    async def _decode_event_data(
        self,
        event_type: EventType,
        topics: List[Any],
        data: str,
        provider: Web3,
    ) -> Dict[str, Any]:
        """Décode les données d'un événement"""
        result = {}

        try:
            # Décode selon le type
            if event_type == EventType.TOKEN_TRANSFERRED:
                # Transfer(address,address,uint256)
                if len(topics) >= 3:
                    result["from"] = "0x" + topics[1][-40:] if hasattr(topics[1], 'hex') else topics[1]
                    result["to"] = "0x" + topics[2][-40:] if hasattr(topics[2], 'hex') else topics[2]
                    if data and data != "0x":
                        result["amount"] = Decimal(str(int(data, 16))) / Decimal(1e18)

            elif event_type == EventType.TOKEN_APPROVED:
                # Approval(address,address,uint256)
                if len(topics) >= 2:
                    result["owner"] = "0x" + topics[1][-40:] if hasattr(topics[1], 'hex') else topics[1]
                    result["spender"] = "0x" + topics[2][-40:] if hasattr(topics[2], 'hex') else topics[2]
                    if data and data != "0x":
                        result["amount"] = Decimal(str(int(data, 16))) / Decimal(1e18)

            elif event_type in [EventType.BRIDGE_INITIATED, EventType.BRIDGE_COMPLETED]:
                # Decodage basique
                if data and data != "0x":
                    # Essayer de décoder les données
                    try:
                        decoded = Web3.to_text(data)
                        result["message"] = decoded
                    except:
                        result["data"] = data

            # Ajout des logs bruts
            result["raw_topics"] = [t.hex() if hasattr(t, 'hex') else t for t in topics]
            result["raw_data"] = data

            return result

        except Exception as e:
            logger.debug(f"Erreur de décodage: {e}")
            return {"error": str(e)}

    def _get_protocol_from_address(self, address: str, chain: str) -> str:
        """Détermine le protocole à partir d'une adresse"""
        # Récupération des configurations de bridges
        bridge_configs = asyncio.run(
            self.bridge_manager.get_all_bridges()
        )

        for config in bridge_configs:
            if (config.chain == chain and
                config.contract_address.lower() == address.lower()):
                return config.protocol.value

        return "unknown"

    # ============================================================
    # MÉTHODES DE TRAITEMENT
    # ============================================================

    async def _queue_event(self, event: BridgeEvent) -> None:
        """Ajoute un événement à la queue"""
        async with self._locks["queue"]:
            self._event_queue.append(event)
            self._event_index[event.event_id] = event
            self._events.append(event)

            # Métriques
            self._event_stats[event.protocol][event.event_type.value] += 1
            self.metrics.record_increment(
                "bridge_events_queued",
                1,
                {
                    "protocol": event.protocol,
                    "chain": event.chain,
                    "event_type": event.event_type.value,
                },
            )

    async def _process_event_queue(self) -> None:
        """Traite la queue d'événements"""
        while self._is_running:
            try:
                if self._event_queue:
                    event = self._event_queue.popleft()
                    await self._process_event(event)
                else:
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Erreur de traitement de la queue: {e}")
                await asyncio.sleep(1)

    async def _process_event(self, event: BridgeEvent) -> None:
        """Traite un événement"""
        try:
            # Vérification du double traitement
            if event.event_id in self._processed_events:
                return

            event.status = EventStatus.PROCESSING
            event.processed_at = datetime.now()

            # 1. Validation de l'événement
            if self.validator:
                validation_result = await self.validator.validate_event(event)
                if not validation_result.is_valid():
                    event.status = EventStatus.FAILED
                    event.error_message = validation_result.message
                    logger.warning(f"Événement invalide: {event.event_id}")
                    return

            # 2. Envoi aux abonnés
            await self._notify_subscribers(event)

            # 3. Envoi aux écouteurs
            await self._notify_listeners(event)

            # 4. Mise à jour du statut
            event.status = EventStatus.PROCESSED
            self._processed_events.add(event.event_id)

            # Métriques
            self.metrics.record_increment(
                "bridge_events_processed",
                1,
                {
                    "protocol": event.protocol,
                    "chain": event.chain,
                    "event_type": event.event_type.value,
                },
            )

        except Exception as e:
            logger.error(f"Erreur de traitement de l'événement {event.event_id}: {e}")
            event.status = EventStatus.FAILED
            event.error_message = str(e)

    async def _notify_subscribers(self, event: BridgeEvent) -> None:
        """Notifie les abonnés"""
        tasks = []

        for subscription in self._subscriptions.values():
            if not subscription.active:
                continue

            # Vérification du filtrage
            if not self._event_matches_subscription(event, subscription):
                continue

            # Appel du callback
            if subscription.callback:
                tasks.append(self._call_callback(subscription.callback, event))

            # Envoi du webhook
            if subscription.webhook_url:
                tasks.append(self._send_webhook(subscription.webhook_url, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _notify_listeners(self, event: BridgeEvent) -> None:
        """Notifie les écouteurs"""
        # Clés de correspondance
        keys = [
            f"{event.event_type.value}:all:all",
            f"{event.event_type.value}:{event.protocol}:all",
            f"{event.event_type.value}:all:{event.chain}",
            f"{event.event_type.value}:{event.protocol}:{event.chain}",
            "all:all:all",
            f"all:{event.protocol}:all",
            f"all:all:{event.chain}",
            f"all:{event.protocol}:{event.chain}",
        ]

        for key in keys:
            if key in self._listeners:
                for callback in self._listeners[key]:
                    await self._call_callback(callback, event)

    async def _call_callback(self, callback: Callable, event: BridgeEvent) -> None:
        """Appelle un callback avec gestion d'erreurs"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            logger.error(f"Erreur de callback: {e}")

    async def _send_webhook(self, webhook_url: str, event: BridgeEvent) -> None:
        """Envoie un webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    webhook_url,
                    json=event.to_dict(),
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception as e:
            logger.error(f"Erreur d'envoi de webhook: {e}")

    def _event_matches_subscription(
        self,
        event: BridgeEvent,
        subscription: EventSubscription,
    ) -> bool:
        """Vérifie si un événement correspond à un abonnement"""
        # Vérification du type
        if event.event_type not in subscription.event_types:
            return False

        # Vérification du protocole
        if subscription.protocols and event.protocol not in subscription.protocols:
            return False

        # Vérification de la chaîne
        if subscription.chains and event.chain not in subscription.chains:
            return False

        # Vérification des adresses
        if subscription.addresses:
            if event.from_address and event.from_address not in subscription.addresses:
                if event.to_address and event.to_address not in subscription.addresses:
                    return False

        return True

    # ============================================================
    # MÉTHODES DE FILTRAGE
    # ============================================================

    async def _apply_filter(
        self,
        events: List[BridgeEvent],
        filter_params: EventFilter,
    ) -> List[BridgeEvent]:
        """Applique un filtre aux événements"""
        filtered = events

        if filter_params.event_types:
            filtered = [
                e for e in filtered
                if e.event_type in filter_params.event_types
            ]

        if filter_params.protocols:
            filtered = [
                e for e in filtered
                if e.protocol in filter_params.protocols
            ]

        if filter_params.chains:
            filtered = [
                e for e in filtered
                if e.chain in filter_params.chains
            ]

        if filter_params.addresses:
            filtered = [
                e for e in filtered
                if (e.from_address and e.from_address in filter_params.addresses) or
                   (e.to_address and e.to_address in filter_params.addresses)
            ]

        if filter_params.tokens:
            filtered = [
                e for e in filtered
                if e.token in filter_params.tokens
            ]

        if filter_params.from_date:
            filtered = [
                e for e in filtered
                if e.timestamp >= filter_params.from_date
            ]

        if filter_params.to_date:
            filtered = [
                e for e in filtered
                if e.timestamp <= filter_params.to_date
            ]

        if filter_params.min_amount:
            filtered = [
                e for e in filtered
                if e.amount and e.amount >= filter_params.min_amount
            ]

        if filter_params.max_amount:
            filtered = [
                e for e in filtered
                if e.amount and e.amount <= filter_params.max_amount
            ]

        if filter_params.statuses:
            filtered = [
                e for e in filtered
                if e.status in filter_params.statuses
            ]

        if filter_params.bridge_ids:
            filtered = [
                e for e in filtered
                if e.bridge_id in filter_params.bridge_ids
            ]

        if filter_params.tx_hashes:
            filtered = [
                e for e in filtered
                if e.tx_hash in filter_params.tx_hashes
            ]

        return filtered

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def _cleanup_events(self) -> None:
        """Nettoie les événements obsolètes"""
        while self._is_running:
            try:
                # Nettoyage des événements de plus de 7 jours
                cutoff = datetime.now() - timedelta(days=7)

                self._events = [
                    e for e in self._events
                    if e.timestamp >= cutoff
                ]

                # Nettoyage des processed events
                if len(self._processed_events) > 10000:
                    self._processed_events.clear()

                # Nettoyage du cache
                current_time = time.time()
                for key in list(self._event_cache.keys()):
                    cached_time, _ = self._event_cache[key]
                    if current_time - cached_time > self.cache_ttl * 2:
                        del self._event_cache[key]

            except Exception as e:
                logger.error(f"Erreur de nettoyage des événements: {e}")

            await asyncio.sleep(3600)  # Toutes les heures

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeEventManager...")

        await self.stop_listening()

        self._events.clear()
        self._event_index.clear()
        self._subscriptions.clear()
        self._event_queue.clear()
        self._processed_events.clear()
        self._listeners.clear()
        self._event_cache.clear()
        self._contract_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_event_manager(
    config: Dict[str, Any],
    bridge_manager: BridgeManager,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> BridgeEventManager:
    """
    Crée une instance de BridgeEventManager

    Args:
        config: Configuration
        bridge_manager: Gestionnaire de bridges
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeEventManager
    """
    return BridgeEventManager(
        config=config,
        bridge_manager=bridge_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeEventManager"""
    # Configuration
    config = {
        "start_block": 10000000,
        "max_events_per_batch": 1000,
        "poll_interval": 2,
        "enabled_protocols": ["wormhole", "layerzero"],
        "enabled_chains": ["ethereum", "polygon"],
    }

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        async def get_all_bridges(self):
            return []

    bridge_manager = SimpleBridgeManager()

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Validateur (simplifié)
    class SimpleValidator:
        async def validate_event(self, event):
            return type('ValidationResult', (), {'is_valid': lambda: True, 'message': ''})()

    validator = SimpleValidator()

    # Création du gestionnaire d'événements
    event_manager = create_bridge_event_manager(
        config=config,
        bridge_manager=bridge_manager,
        web3_providers=web3_providers,
        validator=validator,
    )

    # Ajout d'un écouteur
    async def on_transfer(event):
        print(f"Transfert détecté: {event.amount} {event.token}")

    await event_manager.add_event_listener(
        event_type=EventType.TOKEN_TRANSFERRED,
        callback=on_transfer,
        chain="ethereum",
    )

    # Démarrage de l'écoute
    await event_manager.start_listening()

    # Attendre un peu
    await asyncio.sleep(10)

    # Récupération des événements
    events = await event_manager.get_events(limit=10)
    print(f"Événements récents: {len(events)}")

    # Statistiques
    stats = await event_manager.get_event_stats()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await event_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

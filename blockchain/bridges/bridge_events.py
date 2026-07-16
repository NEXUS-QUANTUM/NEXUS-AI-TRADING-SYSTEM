
# blockchain/bridges/bridge_events.py
"""
NEXUS AI TRADING SYSTEM - Bridge Events Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import json
from typing import Optional, List, Dict, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import queue
import warnings
warnings.filterwarnings('ignore')

try:
    from web3 import Web3
    from web3.contract import Contract
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

logger = logging.getLogger(__name__)


class BridgeEventType(Enum):
    """Types d'événements de bridge"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    CONFIRMATION = "confirmation"
    FAILURE = "failure"
    RETRY = "retry"
    STATUS_CHANGE = "status_change"
    BALANCE_UPDATE = "balance_update"
    GAS_UPDATE = "gas_update"
    ALERT = "alert"
    MAINTENANCE = "maintenance"


@dataclass
class BridgeEvent:
    """Événement de bridge"""
    id: str
    type: BridgeEventType
    bridge_name: str
    data: Dict[str, Any]
    timestamp: datetime
    priority: int = 0
    source: str = ""
    processed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type.value,
            'bridge_name': self.bridge_name,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority,
            'source': self.source,
            'processed': self.processed,
        }


@dataclass
class BridgeEventListener:
    """Listener d'événements de bridge"""
    id: str
    event_types: List[BridgeEventType]
    callback: Callable[[BridgeEvent], None]
    bridge_names: List[str] = field(default_factory=list)
    filter_fn: Optional[Callable[[BridgeEvent], bool]] = None
    active: bool = True
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'event_types': [et.value for et in self.event_types],
            'bridge_names': self.bridge_names,
            'active': self.active,
            'priority': self.priority,
        }


class BridgeEventManager:
    """
    Gestionnaire d'événements pour les bridges.

    Features:
    - Émission d'événements
    - Écoute d'événements
    - Filtrage des événements
    - Queue d'événements
    - Thread-safe

    Example:
        ```python
        manager = BridgeEventManager()

        # Définir un listener
        def on_deposit(event):
            print(f"Deposit: {event.data}")

        manager.add_listener(
            event_types=[BridgeEventType.DEPOSIT],
            callback=on_deposit
        )

        # Émettre un événement
        manager.emit(BridgeEvent(...))

        # Démarrer le traitement
        manager.start()
        ```
    """

    def __init__(self, max_queue_size: int = 1000):
        self.listeners: List[BridgeEventListener] = []
        self.event_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        logger.info(f"BridgeEventManager initialisé")

    def add_listener(
        self,
        callback: Callable[[BridgeEvent], None],
        event_types: Optional[List[BridgeEventType]] = None,
        bridge_names: Optional[List[str]] = None,
        filter_fn: Optional[Callable[[BridgeEvent], bool]] = None,
        priority: int = 0
    ) -> str:
        """
        Ajoute un listener d'événements.

        Args:
            callback: Fonction de callback
            event_types: Types d'événements (tous si None)
            bridge_names: Noms des bridges (tous si None)
            filter_fn: Fonction de filtrage supplémentaire
            priority: Priorité du listener

        Returns:
            str: ID du listener
        """
        import uuid
        listener_id = str(uuid.uuid4())

        listener = BridgeEventListener(
            id=listener_id,
            event_types=event_types or [],
            callback=callback,
            bridge_names=bridge_names or [],
            filter_fn=filter_fn,
            priority=priority,
        )

        with self._lock:
            self.listeners.append(listener)
            self.listeners.sort(key=lambda x: -x.priority)

        logger.info(f"Listener ajouté: {listener_id}")
        return listener_id

    def remove_listener(self, listener_id: str) -> bool:
        """
        Supprime un listener.

        Args:
            listener_id: ID du listener

        Returns:
            bool: True si supprimé
        """
        with self._lock:
            for i, listener in enumerate(self.listeners):
                if listener.id == listener_id:
                    self.listeners.pop(i)
                    logger.info(f"Listener supprimé: {listener_id}")
                    return True

        logger.warning(f"Listener non trouvé: {listener_id}")
        return False

    def emit(self, event: BridgeEvent) -> bool:
        """
        Émet un événement.

        Args:
            event: Événement à émettre

        Returns:
            bool: True si émis
        """
        try:
            self.event_queue.put_nowait(event)
            logger.debug(f"Événement émis: {event.id} ({event.type.value})")
            return True
        except queue.Full:
            logger.warning(f"Queue pleine, événement perdu: {event.id}")
            return False

    def _process_events(self):
        """Traite les événements en continu"""
        while self.is_running:
            try:
                event = self.event_queue.get(timeout=1.0)

                if event is None:
                    continue

                self._dispatch_event(event)
                self.event_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erreur de traitement: {e}")

    def _dispatch_event(self, event: BridgeEvent):
        """
        Dispatch un événement aux listeners.

        Args:
            event: Événement à dispatcher
        """
        with self._lock:
            for listener in self.listeners:
                if not listener.active:
                    continue

                # Vérification du type
                if listener.event_types and event.type not in listener.event_types:
                    continue

                # Vérification du nom du bridge
                if listener.bridge_names and event.bridge_name not in listener.bridge_names:
                    continue

                # Filtrage supplémentaire
                if listener.filter_fn and not listener.filter_fn(event):
                    continue

                try:
                    listener.callback(event)
                except Exception as e:
                    logger.error(f"Erreur dans le callback {listener.id}: {e}")

    def start(self):
        """Démarre le traitement des événements"""
        if self.is_running:
            logger.warning("Déjà en cours d'exécution")
            return

        self.is_running = True
        self._thread = threading.Thread(target=self._process_events, daemon=True)
        self._thread.start()

        logger.info("Gestionnaire d'événements démarré")

    def stop(self):
        """Arrête le traitement des événements"""
        self.is_running = False

        if self._thread:
            self._thread.join(timeout=5)

        logger.info("Gestionnaire d'événements arrêté")

    def clear_queue(self):
        """Vide la queue d'événements"""
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
                self.event_queue.task_done()
            except queue.Empty:
                break

        logger.info("Queue vidée")

    def get_queue_size(self) -> int:
        """
        Retourne la taille de la queue.

        Returns:
            int: Taille de la queue
        """
        return self.event_queue.qsize()

    def get_listeners(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des listeners.

        Returns:
            List[Dict[str, Any]]: Listeners
        """
        with self._lock:
            return [l.to_dict() for l in self.listeners]


class BridgeEventFactory:
    """Factory pour créer des événements de bridge"""

    @staticmethod
    def create_deposit_event(
        bridge_name: str,
        tx_hash: str,
        from_address: str,
        to_address: str,
        amount: float,
        token: str,
        **kwargs
    ) -> BridgeEvent:
        """
        Crée un événement de dépôt.

        Returns:
            BridgeEvent: Événement créé
        """
        import uuid
        return BridgeEvent(
            id=str(uuid.uuid4()),
            type=BridgeEventType.DEPOSIT,
            bridge_name=bridge_name,
            data={
                'tx_hash': tx_hash,
                'from': from_address,
                'to': to_address,
                'amount': amount,
                'token': token,
                **kwargs
            },
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_withdrawal_event(
        bridge_name: str,
        tx_hash: str,
        from_address: str,
        to_address: str,
        amount: float,
        token: str,
        **kwargs
    ) -> BridgeEvent:
        """
        Crée un événement de retrait.

        Returns:
            BridgeEvent: Événement créé
        """
        import uuid
        return BridgeEvent(
            id=str(uuid.uuid4()),
            type=BridgeEventType.WITHDRAWAL,
            bridge_name=bridge_name,
            data={
                'tx_hash': tx_hash,
                'from': from_address,
                'to': to_address,
                'amount': amount,
                'token': token,
                **kwargs
            },
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_confirmation_event(
        bridge_name: str,
        tx_hash: str,
        confirmations: int,
        block_number: int,
        **kwargs
    ) -> BridgeEvent:
        """
        Crée un événement de confirmation.

        Returns:
            BridgeEvent: Événement créé
        """
        import uuid
        return BridgeEvent(
            id=str(uuid.uuid4()),
            type=BridgeEventType.CONFIRMATION,
            bridge_name=bridge_name,
            data={
                'tx_hash': tx_hash,
                'confirmations': confirmations,
                'block_number': block_number,
                **kwargs
            },
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_failure_event(
        bridge_name: str,
        tx_hash: str,
        error: str,
        **kwargs
    ) -> BridgeEvent:
        """
        Crée un événement d'échec.

        Returns:
            BridgeEvent: Événement créé
        """
        import uuid
        return BridgeEvent(
            id=str(uuid.uuid4()),
            type=BridgeEventType.FAILURE,
            bridge_name=bridge_name,
            data={
                'tx_hash': tx_hash,
                'error': error,
                **kwargs
            },
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_alert_event(
        bridge_name: str,
        severity: str,
        message: str,
        **kwargs
    ) -> BridgeEvent:
        """
        Crée un événement d'alerte.

        Returns:
            BridgeEvent: Événement créé
        """
        import uuid
        return BridgeEvent(
            id=str(uuid.uuid4()),
            type=BridgeEventType.ALERT,
            bridge_name=bridge_name,
            data={
                'severity': severity,
                'message': message,
                **kwargs
            },
            timestamp=datetime.now(),
        )


def create_bridge_event_manager(
    max_queue_size: int = 1000
) -> BridgeEventManager:
    """
    Factory pour créer un gestionnaire d'événements de bridge.

    Args:
        max_queue_size: Taille maximale de la queue

    Returns:
        BridgeEventManager: Gestionnaire
    """
    return BridgeEventManager(max_queue_size)


__all__ = [
    'BridgeEventManager',
    'BridgeEvent',
    'BridgeEventListener',
    'BridgeEventType',
    'BridgeEventFactory',
    'create_bridge_event_manager',
]

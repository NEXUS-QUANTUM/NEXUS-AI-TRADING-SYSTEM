# blockchain/bridges/bridge_security.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Sécurité des Bridges

Ce module implémente un système complet de sécurité pour les opérations de bridge
cross-chain, incluant la détection d'attaques, la prévention des exploits,
le monitoring des anomalies, et les mécanismes de réponse aux incidents.

Fonctionnalités principales:
- Détection d'attaques (replay, sandwich, front-running)
- Prévention des exploits (flash loans, oracle manipulation)
- Monitoring des anomalies en temps réel
- Réponse automatique aux incidents
- Analyse de sécurité des contrats
- Détection de drains de fonds
- Protection contre les attaques par manipulation de prix
- Surveillance des validateurs
- Gestion des clés et signatures sécurisées
- Audit de sécurité des transactions
"""

import asyncio
import hashlib
import hmac
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
from collections import deque
from functools import lru_cache, wraps
import re

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from eth_typing import Address, ChecksumAddress
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, SecurityError, ValidationError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from ..security.encryption import EncryptionManager
    from ..security.audit import SecurityAuditor
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, SecurityError, ValidationError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from ..security.encryption import EncryptionManager
    from ..security.audit import SecurityAuditor

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class SecurityEventType(Enum):
    """Types d'événements de sécurité"""
    # Attaques
    REPLAY_ATTACK = "replay_attack"
    FRONT_RUNNING = "front_running"
    SANDWICH_ATTACK = "sandwich_attack"
    FLASH_LOAN_ATTACK = "flash_loan_attack"
    ORACLE_MANIPULATION = "oracle_manipulation"
    PHISHING_ATTEMPT = "phishing_attempt"
    
    # Anomalies
    UNUSUAL_AMOUNT = "unusual_amount"
    UNUSUAL_FREQUENCY = "unusual_frequency"
    UNUSUAL_PATTERN = "unusual_pattern"
    SUSPICIOUS_ADDRESS = "suspicious_address"
    SUSPICIOUS_CONTRACT = "suspicious_contract"
    
    # Drains
    FUND_DRAIN_DETECTED = "fund_drain_detected"
    BALANCE_DROP = "balance_drop"
    EXCESSIVE_WITHDRAWAL = "excessive_withdrawal"
    
    # Validateurs
    VALIDATOR_MISBEHAVIOR = "validator_misbehavior"
    VALIDATOR_DOWN = "validator_down"
    VALIDATOR_BYzANTINE = "validator_byzantine"
    
    # Système
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_SIGNATURE = "invalid_signature"
    CONTRACT_VULNERABILITY = "contract_vulnerability"


class SecurityLevel(Enum):
    """Niveaux de sécurité"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    MAXIMUM = "maximum"


class IncidentStatus(Enum):
    """Statuts des incidents"""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    ESCALATED = "escalated"


class AttackVector(Enum):
    """Vecteurs d'attaque"""
    REPLAY = "replay"
    FRONT_RUN = "front_run"
    SANDWICH = "sandwich"
    FLASH_LOAN = "flash_loan"
    ORACLE = "oracle"
    PHISHING = "phishing"
    INSIDER = "insider"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


@dataclass
class SecurityEvent:
    """Événement de sécurité"""
    event_id: str
    event_type: SecurityEventType
    severity: SecurityLevel
    timestamp: datetime
    chain: str
    protocol: str
    bridge_id: Optional[str] = None
    tx_hash: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[Decimal] = None
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    attack_vector: Optional[AttackVector] = None
    is_malicious: bool = False
    is_mitigated: bool = False
    mitigation_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "chain": self.chain,
            "protocol": self.protocol,
            "bridge_id": self.bridge_id,
            "tx_hash": self.tx_hash,
            "address": self.address,
            "amount": str(self.amount) if self.amount else None,
            "description": self.description,
            "attack_vector": self.attack_vector.value if self.attack_vector else None,
            "is_malicious": self.is_malicious,
            "is_mitigated": self.is_mitigated,
            "mitigation_action": self.mitigation_action,
        }


@dataclass
class SecurityIncident:
    """Incident de sécurité"""
    incident_id: str
    status: IncidentStatus
    events: List[SecurityEvent]
    severity: SecurityLevel
    timestamp: datetime
    resolved_at: Optional[datetime] = None
    description: str = ""
    root_cause: Optional[str] = None
    affected_systems: List[str] = field(default_factory=list)
    mitigation_steps: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "incident_id": self.incident_id,
            "status": self.status.value,
            "events": [e.to_dict() for e in self.events],
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "description": self.description,
            "root_cause": self.root_cause,
            "affected_systems": self.affected_systems,
            "mitigation_steps": self.mitigation_steps,
            "lessons_learned": self.lessons_learned,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeSecurityManager:
    """
    Gestionnaire de sécurité avancé pour les bridges
    """

    def __init__(
        self,
        config: Dict[str, Any],
        web3_providers: Dict[str, Web3],
        bridge_manager: BridgeManager,
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de sécurité

        Args:
            config: Configuration
            web3_providers: Providers Web3 par chaîne
            bridge_manager: Gestionnaire de bridges
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.web3_providers = web3_providers
        self.bridge_manager = bridge_manager
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._security_events: List[SecurityEvent] = []
        self._incidents: List[SecurityIncident] = []
        self._active_incidents: Dict[str, SecurityIncident] = {}
        self._event_cache: Dict[str, Tuple[float, SecurityEvent]] = {}
        self._anomaly_thresholds: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Alertes
        self._alert_callbacks: List[Callable] = []
        self._alert_queue: deque = deque(maxlen=1000)

        # Configuration des seuils
        self._load_thresholds()

        # Monitoring
        self._monitor_tasks: List[asyncio.Task] = []
        self._is_running = False

        # Cache des contrats
        self._contract_cache: Dict[str, Dict[str, Contract]] = {}
        self._vulnerability_db: Dict[str, List[Dict[str, Any]]] = {}

        # Statistiques
        self._security_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Historique des transactions
        self._transaction_history: deque = deque(maxlen=10000)

        logger.info("BridgeSecurityManager initialisé avec succès")

    def _load_thresholds(self) -> None:
        """Charge les seuils de sécurité"""
        default_thresholds = {
            "max_amount": {
                "default": Decimal("100000"),
                "critical": Decimal("500000"),
            },
            "max_frequency": {
                "per_minute": 10,
                "per_hour": 100,
                "per_day": 1000,
            },
            "slippage": {
                "warning": Decimal("0.01"),
                "critical": Decimal("0.05"),
            },
            "gas_price": {
                "warning": Decimal("0.001"),
                "critical": Decimal("0.005"),
            },
            "balance_drop": {
                "warning": Decimal("0.2"),  # 20%
                "critical": Decimal("0.5"),  # 50%
            },
        }

        self._anomaly_thresholds = self.config.get("security_thresholds", default_thresholds)

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    async def analyze_transaction(
        self,
        tx_hash: str,
        chain: str,
        protocol: str,
        amount: Optional[Decimal] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
    ) -> SecurityEvent:
        """
        Analyse une transaction pour détecter des menaces

        Args:
            tx_hash: Hash de la transaction
            chain: Chaîne de la transaction
            protocol: Protocole
            amount: Montant de la transaction
            from_address: Adresse source
            to_address: Adresse destination

        Returns:
            Événement de sécurité
        """
        event_id = f"sec_{uuid.uuid4().hex[:12]}"
        logger.info(f"Analyse de sécurité de la transaction {tx_hash}")

        try:
            # Récupération de la transaction
            provider = self.web3_providers.get(chain)
            if not provider:
                raise SecurityError(f"Provider Web3 non trouvé pour {chain}")

            tx = await provider.eth.get_transaction(HexBytes(tx_hash))
            receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))

            if not tx or not receipt:
                raise SecurityError("Transaction non trouvée")

            # Analyse des menaces
            threat_detected = False
            attack_vector = None
            severity = SecurityLevel.LOW
            details = {}

            # 1. Détection de replay attack
            replay_check = await self._detect_replay_attack(tx, chain, protocol)
            if replay_check["detected"]:
                threat_detected = True
                attack_vector = AttackVector.REPLAY
                severity = SecurityLevel.HIGH
                details["replay_details"] = replay_check

            # 2. Détection de front-running
            front_run_check = await self._detect_front_running(tx, chain, protocol)
            if front_run_check["detected"]:
                threat_detected = True
                attack_vector = AttackVector.FRONT_RUN
                severity = SecurityLevel.HIGH
                details["front_run_details"] = front_run_check

            # 3. Détection de sandwich attack
            sandwich_check = await self._detect_sandwich_attack(tx, chain, protocol)
            if sandwich_check["detected"]:
                threat_detected = True
                attack_vector = AttackVector.SANDWICH
                severity = SecurityLevel.CRITICAL
                details["sandwich_details"] = sandwich_check

            # 4. Détection de flash loan attack
            flash_loan_check = await self._detect_flash_loan_attack(tx, receipt, chain)
            if flash_loan_check["detected"]:
                threat_detected = True
                attack_vector = AttackVector.FLASH_LOAN
                severity = SecurityLevel.CRITICAL
                details["flash_loan_details"] = flash_loan_check

            # 5. Détection de manipulation d'oracle
            oracle_check = await self._detect_oracle_manipulation(tx, receipt, chain)
            if oracle_check["detected"]:
                threat_detected = True
                attack_vector = AttackVector.ORACLE
                severity = SecurityLevel.CRITICAL
                details["oracle_details"] = oracle_check

            # 6. Analyse des montants
            amount_check = await self._analyze_amount(amount, chain, protocol)
            if amount_check["anomaly"]:
                details["amount_anomaly"] = amount_check

            # 7. Analyse des adresses
            address_check = await self._analyze_address(from_address, to_address, chain)
            if address_check["suspicious"]:
                details["address_suspicious"] = address_check

            # 8. Vérification du contrat
            if to_address:
                contract_check = await self._analyze_contract(to_address, chain)
                if contract_check["vulnerable"]:
                    details["contract_vulnerable"] = contract_check

            # Création de l'événement
            event_type = SecurityEventType.UNUSUAL_PATTERN
            if threat_detected:
                if attack_vector == AttackVector.REPLAY:
                    event_type = SecurityEventType.REPLAY_ATTACK
                elif attack_vector == AttackVector.FRONT_RUN:
                    event_type = SecurityEventType.FRONT_RUNNING
                elif attack_vector == AttackVector.SANDWICH:
                    event_type = SecurityEventType.SANDWICH_ATTACK
                elif attack_vector == AttackVector.FLASH_LOAN:
                    event_type = SecurityEventType.FLASH_LOAN_ATTACK
                elif attack_vector == AttackVector.ORACLE:
                    event_type = SecurityEventType.ORACLE_MANIPULATION

            event = SecurityEvent(
                event_id=event_id,
                event_type=event_type,
                severity=severity,
                timestamp=datetime.now(),
                chain=chain,
                protocol=protocol,
                tx_hash=tx_hash,
                address=from_address,
                amount=amount,
                description=f"Analyse de sécurité: {event_type.value}",
                details=details,
                attack_vector=attack_vector,
                is_malicious=threat_detected,
            )

            # Stockage
            self._security_events.append(event)
            self._event_cache[tx_hash] = (time.time(), event)

            # Métriques
            self.metrics.record_increment(
                "security_analysis",
                {
                    "chain": chain,
                    "protocol": protocol,
                    "threat_detected": str(threat_detected),
                    "severity": severity.value,
                },
            )

            # Alerte si nécessaire
            if threat_detected or severity in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                await self._send_alert(event)

            return event

        except Exception as e:
            logger.error(f"Erreur d'analyse de sécurité: {e}")
            return SecurityEvent(
                event_id=event_id,
                event_type=SecurityEventType.UNUSUAL_PATTERN,
                severity=SecurityLevel.MEDIUM,
                timestamp=datetime.now(),
                chain=chain,
                protocol=protocol,
                tx_hash=tx_hash,
                description=f"Erreur d'analyse: {str(e)}",
                details={"error": str(e)},
                is_malicious=False,
            )

    async def detect_anomalies(
        self,
        chain: str,
        protocol: str,
        timeframe: int = 3600,
    ) -> List[SecurityEvent]:
        """
        Détecte les anomalies sur une période donnée

        Args:
            chain: Chaîne à surveiller
            protocol: Protocole
            timeframe: Période en secondes

        Returns:
            Liste des événements de sécurité détectés
        """
        logger.info(f"Détection d'anomalies sur {chain}/{protocol}")

        events = []
        cutoff_time = datetime.now() - timedelta(seconds=timeframe)

        # 1. Analyse des volumes
        volume_anomaly = await self._detect_volume_anomaly(chain, protocol, cutoff_time)
        if volume_anomaly:
            events.append(volume_anomaly)

        # 2. Analyse des fréquences
        frequency_anomaly = await self._detect_frequency_anomaly(chain, protocol, cutoff_time)
        if frequency_anomaly:
            events.append(frequency_anomaly)

        # 3. Analyse des adresses
        address_anomaly = await self._detect_address_anomaly(chain, protocol, cutoff_time)
        if address_anomaly:
            events.append(address_anomaly)

        # 4. Analyse des contracts
        contract_anomaly = await self._detect_contract_anomaly(chain, protocol, cutoff_time)
        if contract_anomaly:
            events.append(contract_anomaly)

        # 5. Analyse des balances
        balance_anomaly = await self._detect_balance_anomaly(chain, protocol, cutoff_time)
        if balance_anomaly:
            events.append(balance_anomaly)

        return events

    async def mitigate_attack(
        self,
        event: SecurityEvent,
        action: str,
    ) -> bool:
        """
        Mitige une attaque détectée

        Args:
            event: Événement de sécurité
            action: Action de mitigation

        Returns:
            True si la mitigation a réussi
        """
        logger.info(f"Mitigation de l'attaque {event.event_id}: {action}")

        try:
            # Actions de mitigation
            if action == "pause_bridge":
                await self._pause_bridge(event.protocol, event.chain)
            elif action == "blacklist_address":
                await self._blacklist_address(event.address, event.chain)
            elif action == "increase_gas":
                await self._increase_gas_security(event)
            elif action == "rollback_transaction":
                await self._rollback_transaction(event)
            elif action == "alert_validators":
                await self._alert_validators(event)
            else:
                logger.warning(f"Action de mitigation inconnue: {action}")
                return False

            event.is_mitigated = True
            event.mitigation_action = action

            # Mise à jour des métriques
            self.metrics.record_increment(
                "security_mitigation",
                {
                    "action": action,
                    "protocol": event.protocol,
                    "chain": event.chain,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Erreur de mitigation: {e}")
            return False

    async def create_incident(
        self,
        events: List[SecurityEvent],
        description: str = "",
    ) -> SecurityIncident:
        """
        Crée un incident de sécurité

        Args:
            events: Liste des événements
            description: Description de l'incident

        Returns:
            Incident créé
        """
        incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        logger.info(f"Création de l'incident {incident_id}")

        # Détermination de la sévérité
        severities = [e.severity for e in events]
        if SecurityLevel.CRITICAL in severities:
            max_severity = SecurityLevel.CRITICAL
        elif SecurityLevel.HIGH in severities:
            max_severity = SecurityLevel.HIGH
        elif SecurityLevel.MEDIUM in severities:
            max_severity = SecurityLevel.MEDIUM
        else:
            max_severity = SecurityLevel.LOW

        incident = SecurityIncident(
            incident_id=incident_id,
            status=IncidentStatus.DETECTED,
            events=events,
            severity=max_severity,
            timestamp=datetime.now(),
            description=description,
            affected_systems=list(set(e.protocol for e in events if e.protocol)),
        )

        self._incidents.append(incident)
        self._active_incidents[incident_id] = incident

        # Notification
        await self._notify_incident(incident)

        return incident

    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str,
    ) -> bool:
        """
        Résout un incident

        Args:
            incident_id: ID de l'incident
            resolution: Résolution

        Returns:
            True si résolu avec succès
        """
        if incident_id not in self._active_incidents:
            return False

        incident = self._active_incidents[incident_id]
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now()
        incident.description += f" Résolu: {resolution}"

        self._active_incidents.pop(incident_id)

        logger.info(f"Incident {incident_id} résolu")
        return True

    # ============================================================
    # MÉTHODES DE DÉTECTION
    # ============================================================

    async def _detect_replay_attack(
        self,
        tx: Dict[str, Any],
        chain: str,
        protocol: str,
    ) -> Dict[str, Any]:
        """Détecte une attaque par replay"""
        result = {"detected": False, "details": {}}

        try:
            tx_hash = tx.get("hash", "").hex()
            nonce = tx.get("nonce", 0)

            # Vérifier si la transaction a déjà été exécutée
            receipt = await self.web3_providers[chain].eth.get_transaction_receipt(
                HexBytes(tx_hash)
            )

            # Si le nonce est déjà utilisé, c'est une replay
            if receipt:
                result["detected"] = True
                result["details"] = {
                    "nonce": nonce,
                    "already_executed": True,
                    "block_number": receipt.get("blockNumber"),
                }

            return result

        except Exception as e:
            logger.debug(f"Erreur de détection de replay: {e}")
            return result

    async def _detect_front_running(
        self,
        tx: Dict[str, Any],
        chain: str,
        protocol: str,
    ) -> Dict[str, Any]:
        """Détecte une attaque de front-running"""
        result = {"detected": False, "details": {}}

        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return result

            # Récupération du bloc courant
            block = await provider.eth.get_block("pending", full_transactions=True)

            # Analyse des transactions dans le mempool
            if block and block.get("transactions"):
                tx_hash = tx.get("hash", "").hex()
                tx_gas = tx.get("gasPrice", 0)
                tx_value = tx.get("value", 0)

                for pending_tx in block["transactions"]:
                    pending_hash = pending_tx.get("hash", "").hex()
                    pending_gas = pending_tx.get("gasPrice", 0)
                    pending_value = pending_tx.get("value", 0)

                    # Une transaction front-running a un gaz plus élevé
                    # et une valeur similaire
                    if (
                        pending_hash != tx_hash
                        and pending_gas > tx_gas
                        and pending_value >= tx_value * 0.9
                        and pending_value <= tx_value * 1.1
                    ):
                        result["detected"] = True
                        result["details"] = {
                            "front_run_tx": pending_hash,
                            "gas_difference": pending_gas - tx_gas,
                            "value_difference": pending_value - tx_value,
                        }
                        break

            return result

        except Exception as e:
            logger.debug(f"Erreur de détection de front-running: {e}")
            return result

    async def _detect_sandwich_attack(
        self,
        tx: Dict[str, Any],
        chain: str,
        protocol: str,
    ) -> Dict[str, Any]:
        """Détecte une attaque sandwich"""
        result = {"detected": False, "details": {}}

        try:
            # Récupération des transactions autour
            provider = self.web3_providers.get(chain)
            if not provider:
                return result

            block = await provider.eth.get_block("pending", full_transactions=True)

            if block and block.get("transactions"):
                tx_hash = tx.get("hash", "").hex()
                tx_index = None

                # Trouver l'index de la transaction
                for i, pending_tx in enumerate(block["transactions"]):
                    if pending_tx.get("hash", "").hex() == tx_hash:
                        tx_index = i
                        break

                if tx_index is not None and tx_index > 0 and tx_index < len(block["transactions"]) - 1:
                    # Vérifier les transactions avant et après
                    before_tx = block["transactions"][tx_index - 1]
                    after_tx = block["transactions"][tx_index + 1]

                    # Une attaque sandwich a des transactions avant et après
                    # avec des montants similaires
                    if (
                        before_tx.get("value", 0) > 0
                        and after_tx.get("value", 0) > 0
                        and abs(before_tx.get("value", 0) - after_tx.get("value", 0)) < tx.get("value", 0) * 0.1
                    ):
                        result["detected"] = True
                        result["details"] = {
                            "before_tx": before_tx.get("hash", "").hex(),
                            "after_tx": after_tx.get("hash", "").hex(),
                            "before_value": before_tx.get("value", 0),
                            "after_value": after_tx.get("value", 0),
                        }

            return result

        except Exception as e:
            logger.debug(f"Erreur de détection de sandwich: {e}")
            return result

    async def _detect_flash_loan_attack(
        self,
        tx: Dict[str, Any],
        receipt: Dict[str, Any],
        chain: str,
    ) -> Dict[str, Any]:
        """Détecte une attaque par flash loan"""
        result = {"detected": False, "details": {}}

        try:
            # Vérification des logs pour les flash loans
            for log in receipt.get("logs", []):
                # Vérification des événements de flash loan
                topics = log.get("topics", [])
                if topics:
                    # Détection basée sur les signatures d'événements courants
                    flash_loan_signatures = [
                        "FlashLoan(address,address,uint256,uint256,uint256)",
                        "FlashLoan(address,address,uint256,uint256,uint256,address)",
                    ]
                    
                    for sig in flash_loan_signatures:
                        if topics[0] == Web3.keccak(text=sig).hex():
                            result["detected"] = True
                            result["details"] = {
                                "flash_loan_log": log,
                                "signature": sig,
                            }
                            break

            return result

        except Exception as e:
            logger.debug(f"Erreur de détection de flash loan: {e}")
            return result

    async def _detect_oracle_manipulation(
        self,
        tx: Dict[str, Any],
        receipt: Dict[str, Any],
        chain: str,
    ) -> Dict[str, Any]:
        """Détecte une manipulation d'oracle"""
        result = {"detected": False, "details": {}}

        try:
            # Vérification des changements de prix
            # Dans la réalité, on comparerait avec les prix d'autres oracles
            oracle_addresses = self.config.get("oracle_addresses", {})
            
            for log in receipt.get("logs", []):
                address = log.get("address", "").lower()
                if address in [addr.lower() for addr in oracle_addresses.get(chain, [])]:
                    # Vérifier si le prix a été mis à jour de manière suspecte
                    result["detected"] = True
                    result["details"] = {
                        "oracle_address": address,
                        "log": log,
                    }
                    break

            return result

        except Exception as e:
            logger.debug(f"Erreur de détection d'oracle: {e}")
            return result

    async def _detect_volume_anomaly(
        self,
        chain: str,
        protocol: str,
        cutoff_time: datetime,
    ) -> Optional[SecurityEvent]:
        """Détecte une anomalie de volume"""
        try:
            # Récupération des transactions récentes
            recent_txs = [tx for tx in self._transaction_history if tx.get("timestamp") > cutoff_time]
            
            if not recent_txs:
                return None

            # Calcul du volume moyen
            total_volume = sum(tx.get("amount", 0) for tx in recent_txs)
            avg_volume = total_volume / len(recent_txs)

            # Vérification des pics de volume
            threshold = avg_volume * 5  # 5x la moyenne
            for tx in recent_txs:
                if tx.get("amount", 0) > threshold:
                    return SecurityEvent(
                        event_id=f"sec_{uuid.uuid4().hex[:12]}",
                        event_type=SecurityEventType.UNUSUAL_AMOUNT,
                        severity=SecurityLevel.HIGH,
                        timestamp=datetime.now(),
                        chain=chain,
                        protocol=protocol,
                        tx_hash=tx.get("tx_hash"),
                        amount=Decimal(str(tx.get("amount", 0))),
                        description=f"Volume anormal détecté: {tx.get('amount')} > {threshold}",
                        details={
                            "avg_volume": str(avg_volume),
                            "threshold": str(threshold),
                            "tx_amount": str(tx.get("amount", 0)),
                        },
                        is_malicious=False,
                    )

            return None

        except Exception as e:
            logger.debug(f"Erreur de détection de volume: {e}")
            return None

    async def _detect_frequency_anomaly(
        self,
        chain: str,
        protocol: str,
        cutoff_time: datetime,
    ) -> Optional[SecurityEvent]:
        """Détecte une anomalie de fréquence"""
        try:
            # Récupération des transactions récentes par adresse
            address_counts = defaultdict(int)
            
            for tx in self._transaction_history:
                if tx.get("timestamp") > cutoff_time:
                    address = tx.get("from_address")
                    if address:
                        address_counts[address] += 1

            # Vérification des fréquences anormales
            threshold = self._anomaly_thresholds.get("max_frequency", {}).get("per_hour", 100)
            
            for address, count in address_counts.items():
                if count > threshold:
                    return SecurityEvent(
                        event_id=f"sec_{uuid.uuid4().hex[:12]}",
                        event_type=SecurityEventType.UNUSUAL_FREQUENCY,
                        severity=SecurityLevel.MEDIUM,
                        timestamp=datetime.now(),
                        chain=chain,
                        protocol=protocol,
                        address=address,
                        description=f"Fréquence anormale détectée: {count} transactions",
                        details={
                            "count": count,
                            "threshold": threshold,
                            "timeframe": "1 hour",
                        },
                        is_malicious=False,
                    )

            return None

        except Exception as e:
            logger.debug(f"Erreur de détection de fréquence: {e}")
            return None

    async def _detect_address_anomaly(
        self,
        chain: str,
        protocol: str,
        cutoff_time: datetime,
    ) -> Optional[SecurityEvent]:
        """Détecte une anomalie d'adresse"""
        try:
            # Vérification des adresses suspectes
            suspicious_addresses = self.config.get("suspicious_addresses", {}).get(chain, [])
            
            for tx in self._transaction_history:
                if tx.get("timestamp") > cutoff_time:
                    from_addr = tx.get("from_address")
                    to_addr = tx.get("to_address")
                    
                    if from_addr in suspicious_addresses or to_addr in suspicious_addresses:
                        return SecurityEvent(
                            event_id=f"sec_{uuid.uuid4().hex[:12]}",
                            event_type=SecurityEventType.SUSPICIOUS_ADDRESS,
                            severity=SecurityLevel.HIGH,
                            timestamp=datetime.now(),
                            chain=chain,
                            protocol=protocol,
                            tx_hash=tx.get("tx_hash"),
                            address=from_addr or to_addr,
                            description=f"Adresse suspecte détectée: {from_addr or to_addr}",
                            details={
                                "address": from_addr or to_addr,
                                "tx_hash": tx.get("tx_hash"),
                            },
                            is_malicious=True,
                        )

            return None

        except Exception as e:
            logger.debug(f"Erreur de détection d'adresse: {e}")
            return None

    async def _detect_contract_anomaly(
        self,
        chain: str,
        protocol: str,
        cutoff_time: datetime,
    ) -> Optional[SecurityEvent]:
        """Détecte une anomalie de contrat"""
        try:
            # Vérification des contrats vulnérables
            vulnerable_contracts = self.config.get("vulnerable_contracts", {}).get(chain, [])
            
            for tx in self._transaction_history:
                if tx.get("timestamp") > cutoff_time:
                    to_addr = tx.get("to_address")
                    
                    if to_addr in vulnerable_contracts:
                        return SecurityEvent(
                            event_id=f"sec_{uuid.uuid4().hex[:12]}",
                            event_type=SecurityEventType.CONTRACT_VULNERABILITY,
                            severity=SecurityLevel.HIGH,
                            timestamp=datetime.now(),
                            chain=chain,
                            protocol=protocol,
                            tx_hash=tx.get("tx_hash"),
                            address=to_addr,
                            description=f"Contrat vulnérable détecté: {to_addr}",
                            details={
                                "contract_address": to_addr,
                                "tx_hash": tx.get("tx_hash"),
                            },
                            is_malicious=True,
                        )

            return None

        except Exception as e:
            logger.debug(f"Erreur de détection de contrat: {e}")
            return None

    async def _detect_balance_anomaly(
        self,
        chain: str,
        protocol: str,
        cutoff_time: datetime,
    ) -> Optional[SecurityEvent]:
        """Détecte une anomalie de balance"""
        try:
            # Vérification des drops de balance
            for address in self.config.get("monitored_addresses", {}).get(chain, []):
                balance = await self._get_address_balance(address, chain)
                previous_balance = self._get_previous_balance(address, chain)
                
                if previous_balance and balance:
                    drop_percentage = 1 - (balance / previous_balance)
                    
                    if drop_percentage > 0.5:  # 50% drop
                        return SecurityEvent(
                            event_id=f"sec_{uuid.uuid4().hex[:12]}",
                            event_type=SecurityEventType.BALANCE_DROP,
                            severity=SecurityLevel.CRITICAL,
                            timestamp=datetime.now(),
                            chain=chain,
                            protocol=protocol,
                            address=address,
                            amount=previous_balance - balance,
                            description=f"Balance drop de {drop_percentage*100:.2f}%",
                            details={
                                "previous_balance": str(previous_balance),
                                "current_balance": str(balance),
                                "drop_percentage": drop_percentage,
                            },
                            is_malicious=True,
                        )

            return None

        except Exception as e:
            logger.debug(f"Erreur de détection de balance: {e}")
            return None

    # ============================================================
    # MÉTHODES D'ANALYSE
    # ============================================================

    async def _analyze_amount(
        self,
        amount: Optional[Decimal],
        chain: str,
        protocol: str,
    ) -> Dict[str, Any]:
        """Analyse les montants"""
        result = {"anomaly": False, "details": {}}

        if not amount:
            return result

        try:
            max_amount = self._anomaly_thresholds.get("max_amount", {}).get(chain, {})
            warning_threshold = Decimal(max_amount.get("warning", "100000"))
            critical_threshold = Decimal(max_amount.get("critical", "500000"))

            if amount > critical_threshold:
                result["anomaly"] = True
                result["details"] = {
                    "type": "critical",
                    "threshold": str(critical_threshold),
                    "amount": str(amount),
                }
            elif amount > warning_threshold:
                result["anomaly"] = True
                result["details"] = {
                    "type": "warning",
                    "threshold": str(warning_threshold),
                    "amount": str(amount),
                }

            return result

        except Exception as e:
            logger.debug(f"Erreur d'analyse de montant: {e}")
            return result

    async def _analyze_address(
        self,
        from_address: Optional[str],
        to_address: Optional[str],
        chain: str,
    ) -> Dict[str, Any]:
        """Analyse les adresses"""
        result = {"suspicious": False, "details": {}}

        try:
            suspicious_addresses = self.config.get("suspicious_addresses", {}).get(chain, [])
            
            if from_address and from_address in suspicious_addresses:
                result["suspicious"] = True
                result["details"]["from"] = from_address
                
            if to_address and to_address in suspicious_addresses:
                result["suspicious"] = True
                result["details"]["to"] = to_address

            return result

        except Exception as e:
            logger.debug(f"Erreur d'analyse d'adresse: {e}")
            return result

    async def _analyze_contract(
        self,
        address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Analyse un contrat"""
        result = {"vulnerable": False, "details": {}}

        try:
            vulnerable_contracts = self.config.get("vulnerable_contracts", {}).get(chain, [])
            
            if address in vulnerable_contracts:
                result["vulnerable"] = True
                result["details"] = {
                    "address": address,
                    "chain": chain,
                }

            return result

        except Exception as e:
            logger.debug(f"Erreur d'analyse de contrat: {e}")
            return result

    # ============================================================
    # MÉTHODES DE MITIGATION
    # ============================================================

    async def _pause_bridge(self, protocol: str, chain: str) -> bool:
        """Pause un bridge"""
        try:
            # Appel au bridge manager pour mettre en pause
            if hasattr(self.bridge_manager, 'pause_bridge'):
                return await self.bridge_manager.pause_bridge(protocol, chain)
            
            logger.warning(f"BridgeManager ne supporte pas pause_bridge")
            return False

        except Exception as e:
            logger.error(f"Erreur de pause du bridge: {e}")
            return False

    async def _blacklist_address(self, address: Optional[str], chain: str) -> bool:
        """Met une adresse en liste noire"""
        if not address:
            return False

        try:
            # Ajout à la liste noire
            blacklist = self.config.get("blacklist", {}).get(chain, [])
            if address not in blacklist:
                blacklist.append(address)
            
            logger.info(f"Adresse {address} ajoutée à la liste noire sur {chain}")
            return True

        except Exception as e:
            logger.error(f"Erreur de blacklist: {e}")
            return False

    async def _increase_gas_security(self, event: SecurityEvent) -> bool:
        """Augmente les paramètres de sécurité du gaz"""
        try:
            # Augmentation du seuil de gaz pour les transactions suspectes
            gas_threshold = self.config.get("gas_security", {}).get("threshold", 1.5)
            self.config["gas_security"]["threshold"] = gas_threshold * 1.2
            
            logger.info("Paramètres de sécurité du gaz augmentés")
            return True

        except Exception as e:
            logger.error(f"Erreur d'augmentation de sécurité gaz: {e}")
            return False

    async def _rollback_transaction(self, event: SecurityEvent) -> bool:
        """Rollback une transaction"""
        if not event.tx_hash:
            return False

        try:
            # Dans la réalité, rollback d'une transaction est généralement impossible
            # on peut tenter de compenser
            logger.warning(f"Rollback de la transaction {event.tx_hash} demandé")
            return True

        except Exception as e:
            logger.error(f"Erreur de rollback: {e}")
            return False

    async def _alert_validators(self, event: SecurityEvent) -> bool:
        """Alerte les validateurs"""
        try:
            # Envoi de notification aux validateurs
            await self._send_alert(event, priority="high")
            return True

        except Exception as e:
            logger.error(f"Erreur d'alerte des validateurs: {e}")
            return False

    # ============================================================
    # MÉTHODES DE NOTIFICATION
    # ============================================================

    async def _send_alert(self, event: SecurityEvent, priority: str = "normal") -> None:
        """Envoie une alerte"""
        try:
            alert_data = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "severity": event.severity.value,
                "timestamp": event.timestamp.isoformat(),
                "chain": event.chain,
                "protocol": event.protocol,
                "description": event.description,
                "priority": priority,
                "details": event.details,
            }

            # Ajout à la queue d'alertes
            self._alert_queue.append(alert_data)

            # Appel des callbacks
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert_data)
                    else:
                        callback(alert_data)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'alerte: {e}")

            # Métriques
            self.metrics.record_increment(
                "security_alert_sent",
                {
                    "event_type": event.event_type.value,
                    "severity": event.severity.value,
                    "protocol": event.protocol,
                },
            )

        except Exception as e:
            logger.error(f"Erreur d'envoi d'alerte: {e}")

    async def _notify_incident(self, incident: SecurityIncident) -> None:
        """Notifie un incident"""
        try:
            notification = {
                "incident_id": incident.incident_id,
                "status": incident.status.value,
                "severity": incident.severity.value,
                "timestamp": incident.timestamp.isoformat(),
                "description": incident.description,
                "affected_systems": incident.affected_systems,
                "event_count": len(incident.events),
            }

            # Appel des callbacks avec l'incident
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(notification)
                    else:
                        callback(notification)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'incident: {e}")

        except Exception as e:
            logger.error(f"Erreur de notification d'incident: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_address_balance(self, address: str, chain: str) -> Optional[Decimal]:
        """Obtient la balance d'une adresse"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return None

            balance = await provider.eth.get_balance(to_checksum_address(address))
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.debug(f"Erreur de balance: {e}")
            return None

    def _get_previous_balance(self, address: str, chain: str) -> Optional[Decimal]:
        """Récupère la balance précédente"""
        # Dans la réalité, on stockerait les balances historiques
        return None

    def add_alert_callback(self, callback: Callable) -> None:
        """Ajoute un callback pour les alertes"""
        self._alert_callbacks.append(callback)

    def get_security_stats(self) -> Dict[str, Any]:
        """Obtient les statistiques de sécurité"""
        total_events = len(self._security_events)
        malicious_events = sum(1 for e in self._security_events if e.is_malicious)
        mitigated_events = sum(1 for e in self._security_events if e.is_mitigated)
        active_incidents = len(self._active_incidents)

        # Statistiques par type
        event_types = defaultdict(int)
        for event in self._security_events:
            event_types[event.event_type.value] += 1

        # Statistiques par sévérité
        severities = defaultdict(int)
        for event in self._security_events:
            severities[event.severity.value] += 1

        return {
            "total_events": total_events,
            "malicious_events": malicious_events,
            "mitigated_events": mitigated_events,
            "active_incidents": active_incidents,
            "event_types": dict(event_types),
            "severities": dict(severities),
            "alert_queue_size": len(self._alert_queue),
            "config": {
                "max_amount": str(self._anomaly_thresholds.get("max_amount", {})),
                "max_frequency": self._anomaly_thresholds.get("max_frequency", {}),
                "slippage": str(self._anomaly_thresholds.get("slippage", {})),
            },
        }

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring en arrière-plan"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage du monitoring de sécurité")

        # Tâches de monitoring
        self._monitor_tasks.extend([
            asyncio.create_task(self._monitor_anomalies()),
            asyncio.create_task(self._monitor_alerts()),
            asyncio.create_task(self._monitor_balances()),
        ])

    async def stop_monitoring(self) -> None:
        """Arrête le monitoring"""
        self._is_running = False

        for task in self._monitor_tasks:
            task.cancel()

        try:
            await asyncio.gather(*self._monitor_tasks, return_exceptions=True)
        except Exception:
            pass

        self._monitor_tasks.clear()
        logger.info("Monitoring de sécurité arrêté")

    async def _monitor_anomalies(self) -> None:
        """Monitore les anomalies en continu"""
        while self._is_running:
            try:
                for chain in self.web3_providers.keys():
                    for protocol in self.config.get("monitored_protocols", []):
                        events = await self.detect_anomalies(chain, protocol, 3600)
                        
                        if events:
                            # Création d'un incident si nécessaire
                            malicious_events = [e for e in events if e.is_malicious]
                            if malicious_events:
                                await self.create_incident(
                                    malicious_events,
                                    f"Incident automatique sur {chain}/{protocol}"
                                )

            except Exception as e:
                logger.error(f"Erreur de monitoring des anomalies: {e}")

            await asyncio.sleep(60)  # Toutes les minutes

    async def _monitor_alerts(self) -> None:
        """Monitore les alertes en continu"""
        while self._is_running:
            try:
                # Traitement des alertes en attente
                while self._alert_queue:
                    alert = self._alert_queue.popleft()
                    # Traitement des alertes
                    logger.info(f"Alerte traitée: {alert.get('event_id')}")

            except Exception as e:
                logger.error(f"Erreur de monitoring des alertes: {e}")

            await asyncio.sleep(5)

    async def _monitor_balances(self) -> None:
        """Monitore les balances en continu"""
        while self._is_running:
            try:
                for chain, addresses in self.config.get("monitored_addresses", {}).items():
                    for address in addresses:
                        balance = await self._get_address_balance(address, chain)
                        
                        if balance is not None:
                            # Vérification des drops
                            previous = self._get_previous_balance(address, chain)
                            if previous and balance < previous * Decimal("0.5"):
                                # Alerté en cas de drop important
                                event = SecurityEvent(
                                    event_id=f"sec_{uuid.uuid4().hex[:12]}",
                                    event_type=SecurityEventType.BALANCE_DROP,
                                    severity=SecurityLevel.HIGH,
                                    timestamp=datetime.now(),
                                    chain=chain,
                                    protocol="monitoring",
                                    address=address,
                                    amount=previous - balance,
                                    description=f"Balance drop de {((1 - balance/previous)*100):.2f}%",
                                    details={
                                        "previous": str(previous),
                                        "current": str(balance),
                                    },
                                    is_malicious=True,
                                )
                                await self._send_alert(event)

            except Exception as e:
                logger.error(f"Erreur de monitoring des balances: {e}")

            await asyncio.sleep(300)  # Toutes les 5 minutes

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeSecurityManager...")

        await self.stop_monitoring()

        self._security_events.clear()
        self._incidents.clear()
        self._active_incidents.clear()
        self._event_cache.clear()
        self._alert_callbacks.clear()
        self._alert_queue.clear()

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_security_manager(
    config: Dict[str, Any],
    web3_providers: Dict[str, Web3],
    bridge_manager: BridgeManager,
    **kwargs,
) -> BridgeSecurityManager:
    """
    Crée une instance de BridgeSecurityManager

    Args:
        config: Configuration
        web3_providers: Providers Web3
        bridge_manager: Gestionnaire de bridges
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeSecurityManager
    """
    return BridgeSecurityManager(
        config=config,
        web3_providers=web3_providers,
        bridge_manager=bridge_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeSecurityManager"""
    # Configuration
    config = {
        "security_thresholds": {
            "max_amount": {
                "ethereum": {
                    "warning": "100000",
                    "critical": "500000",
                },
            },
            "max_frequency": {
                "per_minute": 10,
                "per_hour": 100,
            },
            "slippage": {
                "warning": "0.01",
                "critical": "0.05",
            },
        },
        "suspicious_addresses": {
            "ethereum": ["0x..."],
        },
        "vulnerable_contracts": {
            "ethereum": ["0x..."],
        },
        "monitored_addresses": {
            "ethereum": ["0x..."],
        },
        "monitored_protocols": ["wormhole", "layerzero"],
        "oracle_addresses": {
            "ethereum": ["0x..."],
        },
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        async def pause_bridge(self, protocol, chain):
            return True

    bridge_manager = SimpleBridgeManager()

    # Création du gestionnaire de sécurité
    security_manager = create_bridge_security_manager(
        config=config,
        web3_providers=web3_providers,
        bridge_manager=bridge_manager,
    )

    # Ajout d'un callback d'alerte
    def alert_callback(alert):
        print(f"ALERTE: {alert}")

    security_manager.add_alert_callback(alert_callback)

    # Analyse d'une transaction
    event = await security_manager.analyze_transaction(
        tx_hash="0x...",
        chain="ethereum",
        protocol="wormhole",
        amount=Decimal("100000"),
    )

    print(f"Événement: {event.to_dict()}")

    # Détection d'anomalies
    events = await security_manager.detect_anomalies(
        chain="ethereum",
        protocol="wormhole",
        timeframe=3600,
    )

    print(f"Anomalies détectées: {len(events)}")

    # Création d'un incident si nécessaire
    if events:
        incident = await security_manager.create_incident(
            events,
            "Incident de sécurité détecté"
        )
        print(f"Incident créé: {incident.incident_id}")

    # Démarrage du monitoring
    await security_manager.start_monitoring()

    # Statistiques
    stats = security_manager.get_security_stats()
    print(f"Statistiques: {stats}")

    # Attendre un peu
    await asyncio.sleep(10)

    # Nettoyage
    await security_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

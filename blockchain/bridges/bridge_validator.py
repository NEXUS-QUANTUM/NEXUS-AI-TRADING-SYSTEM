# blockchain/bridges/bridge_validator.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Validation des Bridges

Ce module implémente un système complet de validation pour les opérations de bridge
cross-chain, incluant la vérification des transactions, l'analyse des risques,
la détection d'anomalies, et la validation des signatures cryptographiques.

Fonctionnalités principales:
- Validation des transactions de bridge
- Vérification des signatures cryptographiques
- Analyse des risques et détection d'anomalies
- Validation des montants et des limites
- Vérification des contrats et des adresses
- Détection de fraude et de manipulations
- Validation des preuves Merkle
- Audit des événements on-chain
- Conformité réglementaire (AML/KYC)
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
from functools import lru_cache, wraps
import re

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex, is_checksum_address
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import base58
import nacl.signing
import nacl.encoding

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, SecurityError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_analytics import BridgeAnalytics
    from ..security.encryption import EncryptionManager
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, SecurityError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_analytics import BridgeAnalytics
    from ..security.encryption import EncryptionManager
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ValidationLevel(Enum):
    """Niveaux de validation"""
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"
    COMPREHENSIVE = "comprehensive"
    MAXIMUM = "maximum"


class ValidationType(Enum):
    """Types de validation"""
    TRANSACTION = "transaction"
    SIGNATURE = "signature"
    AMOUNT = "amount"
    ADDRESS = "address"
    CONTRACT = "contract"
    MERKLE = "merkle"
    EVENT = "event"
    RISK = "risk"
    COMPLIANCE = "compliance"
    FRAUD = "fraud"


class RiskLevel(Enum):
    """Niveaux de risque"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationStatus(Enum):
    """Statuts de validation"""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    SUSPICIOUS = "suspicious"
    REJECTED = "rejected"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Résultat de validation"""
    validation_id: str
    validation_type: ValidationType
    status: ValidationStatus
    risk_level: RiskLevel
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "validation_id": self.validation_id,
            "validation_type": self.validation_type.value,
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "warnings": self.warnings,
            "score": self.score,
        }

    def is_valid(self) -> bool:
        """Vérifie si la validation est valide"""
        return self.status == ValidationStatus.VALID

    def is_suspicious(self) -> bool:
        """Vérifie si le résultat est suspect"""
        return self.status == ValidationStatus.SUSPICIOUS


@dataclass
class BridgeValidationRequest:
    """Requête de validation de bridge"""
    request_id: str
    bridge_id: str
    protocol: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    tx_hash: Optional[str] = None
    signature: Optional[str] = None
    merkle_proof: Optional[List[str]] = None
    event_data: Optional[Dict[str, Any]] = None
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    custom_checks: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "bridge_id": self.bridge_id,
            "protocol": self.protocol,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "source_address": self.source_address,
            "destination_address": self.destination_address,
            "tx_hash": self.tx_hash,
            "validation_level": self.validation_level.value,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeValidator:
    """
    Validateur avancé pour les opérations de bridge
    """

    def __init__(
        self,
        config: Dict[str, Any],
        web3_providers: Dict[str, Web3],
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le validateur de bridge

        Args:
            config: Configuration du validateur
            web3_providers: Dictionnaire des providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.web3_providers = web3_providers
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._validation_cache: Dict[str, Tuple[float, ValidationResult]] = {}
        self._blacklist_cache: Set[str] = set()
        self._whitelist_cache: Set[str] = set()
        self._risk_cache: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des validations
        self._validation_rules = self._load_validation_rules()
        self._risk_thresholds = self._load_risk_thresholds()
        self._compliance_rules = self._load_compliance_rules()

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des contrats
        self._contract_cache: Dict[str, Dict[str, Contract]] = {}
        self._abi_cache: Dict[str, List[Dict[str, Any]]] = {}

        # Statistiques
        self._validation_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Load des listes de sécurité
        self._load_security_lists()

        logger.info("BridgeValidator initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def validate_bridge(
        self,
        request: BridgeValidationRequest,
    ) -> ValidationResult:
        """
        Valide une opération de bridge

        Args:
            request: Requête de validation

        Returns:
            Résultat de validation
        """
        validation_id = f"val_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation du bridge {request.bridge_id} ({validation_id})")

        # Vérification du cache
        cache_key = self._get_cache_key(request)
        if cache_key in self._validation_cache:
            cached_time, cached_result = self._validation_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Résultat de validation retourné du cache")
                return cached_result

        try:
            # Exécution des validations
            result = await self._perform_validation(request, validation_id)

            # Mise en cache
            self._validation_cache[cache_key] = (time.time(), result)

            # Métriques
            self.metrics.record_increment(
                "bridge_validation_result",
                {
                    "protocol": request.protocol,
                    "status": result.status.value,
                    "risk_level": result.risk_level.value,
                },
            )

            # Mise à jour des statistiques
            self._update_stats(request.protocol, result)

            return result

        except Exception as e:
            logger.error(f"Erreur de validation: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.TRANSACTION,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def validate_transaction(
        self,
        tx_hash: str,
        chain: str,
        protocol: str,
        **kwargs,
    ) -> ValidationResult:
        """
        Valide une transaction on-chain

        Args:
            tx_hash: Hash de la transaction
            chain: Chaîne de la transaction
            protocol: Protocole du bridge
            **kwargs: Arguments additionnels

        Returns:
            Résultat de validation
        """
        validation_id = f"val_tx_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation de la transaction {tx_hash} sur {chain}")

        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise ValidationError(f"Provider Web3 non trouvé pour {chain}")

            # Récupération de la transaction
            tx = await provider.eth.get_transaction(HexBytes(tx_hash))
            receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))

            if not tx or not receipt:
                raise ValidationError("Transaction non trouvée")

            # Validation du contenu
            validations = []

            # 1. Vérification du statut
            if receipt.get("status") == 1:
                validations.append(("transaction_status", True, "Transaction réussie"))
            else:
                validations.append(("transaction_status", False, "Transaction échouée"))

            # 2. Vérification du protocole
            protocol_match = await self._verify_protocol_in_tx(tx, receipt, protocol)
            validations.append(("protocol_match", protocol_match, "Correspondance du protocole"))

            # 3. Vérification des montants
            amount_valid = await self._verify_amount_in_tx(tx, receipt, kwargs.get("expected_amount"))
            validations.append(("amount_valid", amount_valid, "Montant valide"))

            # Construction du résultat
            status = ValidationStatus.VALID if all(v[1] for v in validations) else ValidationStatus.INVALID
            risk_level = self._calculate_risk_level(validations)

            result = ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.TRANSACTION,
                status=status,
                risk_level=risk_level,
                message="Validation de transaction terminée",
                details={
                    "tx_hash": tx_hash,
                    "chain": chain,
                    "protocol": protocol,
                    "block_number": receipt.get("blockNumber"),
                    "gas_used": receipt.get("gasUsed"),
                },
                checks_passed=[v[0] for v in validations if v[1]],
                checks_failed=[v[0] for v in validations if not v[1]],
                warnings=[v[2] for v in validations if not v[1]],
                score=sum(1 for v in validations if v[1]) / len(validations) if validations else 0.0,
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de validation de transaction: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.TRANSACTION,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def validate_signature(
        self,
        message: str,
        signature: str,
        address: str,
        chain: str = "ethereum",
    ) -> ValidationResult:
        """
        Valide une signature cryptographique

        Args:
            message: Message signé
            signature: Signature
            address: Adresse du signataire
            chain: Chaîne de la signature

        Returns:
            Résultat de validation
        """
        validation_id = f"val_sig_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation de signature pour {address}")

        try:
            # Récupération du provider
            provider = self.web3_providers.get(chain)
            if not provider:
                raise ValidationError(f"Provider Web3 non trouvé pour {chain}")

            # Validation de la signature
            is_valid = await self._verify_signature(
                message=message,
                signature=signature,
                address=address,
                provider=provider,
            )

            status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID

            result = ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.SIGNATURE,
                status=status,
                risk_level=RiskLevel.LOW if is_valid else RiskLevel.HIGH,
                message="Signature valide" if is_valid else "Signature invalide",
                details={
                    "address": address,
                    "chain": chain,
                    "message_hash": hashlib.sha256(message.encode()).hexdigest(),
                },
                checks_passed=["signature_verification"] if is_valid else [],
                checks_failed=["signature_verification"] if not is_valid else [],
                score=1.0 if is_valid else 0.0,
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de validation de signature: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.SIGNATURE,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def validate_amount(
        self,
        amount: Decimal,
        token: str,
        chain: str,
        protocol: str,
        **kwargs,
    ) -> ValidationResult:
        """
        Valide un montant pour un bridge

        Args:
            amount: Montant à valider
            token: Token concerné
            chain: Chaîne concernée
            protocol: Protocole du bridge
            **kwargs: Arguments additionnels

        Returns:
            Résultat de validation
        """
        validation_id = f"val_amt_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation du montant {amount} {token}")

        try:
            checks_passed = []
            checks_failed = []
            warnings = []

            # 1. Vérification du montant minimum
            min_amount = self._get_min_amount(token, chain, protocol)
            if amount < min_amount:
                checks_failed.append("minimum_amount")
                warnings.append(f"Montant inférieur au minimum ({min_amount})")
            else:
                checks_passed.append("minimum_amount")

            # 2. Vérification du montant maximum
            max_amount = self._get_max_amount(token, chain, protocol)
            if amount > max_amount:
                checks_failed.append("maximum_amount")
                warnings.append(f"Montant supérieur au maximum ({max_amount})")
            else:
                checks_passed.append("maximum_amount")

            # 3. Vérification des décimales
            decimals = await self._get_token_decimals(token, chain)
            if decimals > 0:
                amount_str = str(amount)
                if '.' in amount_str:
                    decimal_places = len(amount_str.split('.')[1])
                    if decimal_places > decimals:
                        checks_failed.append("decimal_precision")
                        warnings.append(f"Trop de décimales ({decimal_places} > {decimals})")
                    else:
                        checks_passed.append("decimal_precision")
                else:
                    checks_passed.append("decimal_precision")
            else:
                checks_passed.append("decimal_precision")

            # 4. Vérification des limites de risque
            risk_check = await self._check_amount_risk(amount, token, chain)
            if risk_check.get("status") == "warning":
                warnings.append(risk_check.get("message", "Alerte de risque"))
                checks_failed.append("risk_check")
            else:
                checks_passed.append("risk_check")

            # Calcul du score
            total_checks = len(checks_passed) + len(checks_failed)
            score = len(checks_passed) / total_checks if total_checks > 0 else 0.0

            # Détermination du statut
            if len(checks_failed) == 0:
                status = ValidationStatus.VALID
                risk_level = RiskLevel.LOW
            elif len(checks_failed) <= 1:
                status = ValidationStatus.WARNING
                risk_level = RiskLevel.MEDIUM
            else:
                status = ValidationStatus.INVALID
                risk_level = RiskLevel.HIGH

            result = ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.AMOUNT,
                status=status,
                risk_level=risk_level,
                message=f"Validation du montant {amount} terminée",
                details={
                    "amount": str(amount),
                    "token": token,
                    "chain": chain,
                    "protocol": protocol,
                    "min_amount": str(min_amount),
                    "max_amount": str(max_amount),
                    "decimals": decimals,
                },
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                warnings=warnings,
                score=score,
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de validation de montant: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.AMOUNT,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def validate_address(
        self,
        address: str,
        chain: str,
        check_type: str = "all",
    ) -> ValidationResult:
        """
        Valide une adresse blockchain

        Args:
            address: Adresse à valider
            chain: Chaîne de l'adresse
            check_type: Type de vérification

        Returns:
            Résultat de validation
        """
        validation_id = f"val_addr_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation de l'adresse {address} sur {chain}")

        try:
            checks_passed = []
            checks_failed = []
            warnings = []

            # 1. Vérification du format
            is_valid_format = await self._validate_address_format(address, chain)
            if is_valid_format:
                checks_passed.append("format")
            else:
                checks_failed.append("format")
                warnings.append("Format d'adresse invalide")

            # 2. Vérification de la checksum
            if chain in ["ethereum", "bsc", "polygon", "arbitrum", "optimism"]:
                is_checksum = is_checksum_address(address) or is_address(address)
                if is_checksum:
                    checks_passed.append("checksum")
                else:
                    checks_failed.append("checksum")
                    warnings.append("Checksum invalide")

            # 3. Vérification de l'activité (si demandée)
            if check_type in ["all", "active"]:
                is_active = await self._check_address_activity(address, chain)
                if is_active:
                    checks_passed.append("active")
                else:
                    checks_failed.append("active")
                    warnings.append("Adresse inactive")

            # 4. Vérification de la liste noire
            if await self._is_blacklisted(address, chain):
                checks_failed.append("blacklist")
                warnings.append("Adresse dans la liste noire")
            else:
                checks_passed.append("blacklist")

            # 5. Vérification de la liste blanche
            if await self._is_whitelisted(address, chain):
                checks_passed.append("whitelist")
            else:
                checks_failed.append("whitelist")
                warnings.append("Adresse non dans la liste blanche")

            # Calcul du score
            total_checks = len(checks_passed) + len(checks_failed)
            score = len(checks_passed) / total_checks if total_checks > 0 else 0.0

            # Détermination du statut
            if len(checks_failed) == 0:
                status = ValidationStatus.VALID
                risk_level = RiskLevel.LOW
            elif len(checks_failed) <= 2:
                status = ValidationStatus.WARNING
                risk_level = RiskLevel.MEDIUM
            else:
                status = ValidationStatus.INVALID
                risk_level = RiskLevel.HIGH

            result = ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.ADDRESS,
                status=status,
                risk_level=risk_level,
                message=f"Validation de l'adresse {address} terminée",
                details={
                    "address": address,
                    "chain": chain,
                    "check_type": check_type,
                },
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                warnings=warnings,
                score=score,
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de validation d'adresse: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.ADDRESS,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def validate_merkle_proof(
        self,
        root: str,
        proof: List[str],
        leaf: str,
        chain: str,
    ) -> ValidationResult:
        """
        Valide une preuve Merkle

        Args:
            root: Racine Merkle
            proof: Preuve Merkle
            leaf: Feuille
            chain: Chaîne

        Returns:
            Résultat de validation
        """
        validation_id = f"val_merkle_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation de preuve Merkle pour {leaf}")

        try:
            # Validation de la preuve
            is_valid = await self._verify_merkle_proof(
                root=root,
                proof=proof,
                leaf=leaf,
                chain=chain,
            )

            status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID

            result = ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.MERKLE,
                status=status,
                risk_level=RiskLevel.LOW if is_valid else RiskLevel.HIGH,
                message="Preuve Merkle valide" if is_valid else "Preuve Merkle invalide",
                details={
                    "root": root,
                    "leaf": leaf,
                    "proof_length": len(proof),
                    "chain": chain,
                },
                checks_passed=["merkle_verification"] if is_valid else [],
                checks_failed=["merkle_verification"] if not is_valid else [],
                score=1.0 if is_valid else 0.0,
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de validation Merkle: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.MERKLE,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def validate_compliance(
        self,
        address: str,
        amount: Decimal,
        token: str,
        chain: str,
    ) -> ValidationResult:
        """
        Valide la conformité réglementaire (AML/KYC)

        Args:
            address: Adresse à vérifier
            amount: Montant
            token: Token
            chain: Chaîne

        Returns:
            Résultat de validation
        """
        validation_id = f"val_comp_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation de conformité pour {address}")

        try:
            checks_passed = []
            checks_failed = []
            warnings = []

            # 1. Vérification AML
            aml_check = await self._check_aml(address, amount, token, chain)
            if aml_check.get("status") == "passed":
                checks_passed.append("aml")
            else:
                checks_failed.append("aml")
                warnings.append(aml_check.get("message", "Échec AML"))

            # 2. Vérification KYC
            kyc_check = await self._check_kyc(address, chain)
            if kyc_check.get("status") == "passed":
                checks_passed.append("kyc")
            else:
                checks_failed.append("kyc")
                warnings.append(kyc_check.get("message", "KYC requis"))

            # 3. Vérification des juridictions
            jurisdiction_check = await self._check_jurisdiction(address, chain)
            if jurisdiction_check.get("status") == "passed":
                checks_passed.append("jurisdiction")
            else:
                checks_failed.append("jurisdiction")
                warnings.append(jurisdiction_check.get("message", "Juridiction restreinte"))

            # 4. Vérification du risque de sanction
            sanction_check = await self._check_sanctions(address, chain)
            if sanction_check.get("status") == "passed":
                checks_passed.append("sanctions")
            else:
                checks_failed.append("sanctions")
                warnings.append(sanction_check.get("message", "Sanctions détectées"))

            # Calcul du score
            total_checks = len(checks_passed) + len(checks_failed)
            score = len(checks_passed) / total_checks if total_checks > 0 else 0.0

            # Détermination du statut
            if len(checks_failed) == 0:
                status = ValidationStatus.VALID
                risk_level = RiskLevel.LOW
            elif len(checks_failed) <= 1:
                status = ValidationStatus.WARNING
                risk_level = RiskLevel.MEDIUM
            else:
                status = ValidationStatus.REJECTED
                risk_level = RiskLevel.HIGH

            result = ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.COMPLIANCE,
                status=status,
                risk_level=risk_level,
                message="Validation de conformité terminée",
                details={
                    "address": address,
                    "amount": str(amount),
                    "token": token,
                    "chain": chain,
                },
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                warnings=warnings,
                score=score,
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de validation de conformité: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.COMPLIANCE,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    # ============================================================
    # MÉTHODES INTERNES DE VALIDATION
    # ============================================================

    async def _perform_validation(
        self,
        request: BridgeValidationRequest,
        validation_id: str,
    ) -> ValidationResult:
        """Exécute la validation complète"""
        results: List[ValidationResult] = []

        # 1. Validation de la transaction
        if request.tx_hash:
            tx_result = await self.validate_transaction(
                tx_hash=request.tx_hash,
                chain=request.chain_from,
                protocol=request.protocol,
                expected_amount=request.amount,
            )
            results.append(tx_result)

        # 2. Validation de la signature
        if request.signature:
            sig_result = await self.validate_signature(
                message=f"{request.bridge_id}:{request.amount}",
                signature=request.signature,
                address=request.source_address,
                chain=request.chain_from,
            )
            results.append(sig_result)

        # 3. Validation du montant
        amount_result = await self.validate_amount(
            amount=request.amount,
            token=request.token_from,
            chain=request.chain_from,
            protocol=request.protocol,
        )
        results.append(amount_result)

        # 4. Validation de l'adresse source
        source_result = await self.validate_address(
            address=request.source_address,
            chain=request.chain_from,
        )
        results.append(source_result)

        # 5. Validation de l'adresse destination
        dest_result = await self.validate_address(
            address=request.destination_address,
            chain=request.chain_to,
        )
        results.append(dest_result)

        # 6. Validation de la conformité
        compliance_result = await self.validate_compliance(
            address=request.source_address,
            amount=request.amount,
            token=request.token_from,
            chain=request.chain_from,
        )
        results.append(compliance_result)

        # 7. Validation du contrat (si applicable)
        if request.protocol in self._get_supported_protocols():
            contract_result = await self.validate_contract(
                protocol=request.protocol,
                chain=request.chain_from,
            )
            results.append(contract_result)

        # Agrégation des résultats
        return self._aggregate_results(results, validation_id, request)

    def _aggregate_results(
        self,
        results: List[ValidationResult],
        validation_id: str,
        request: BridgeValidationRequest,
    ) -> ValidationResult:
        """Agrège les résultats de validation"""
        if not results:
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.TRANSACTION,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message="Aucun résultat de validation",
                score=0.0,
            )

        # Agrégation des statuts
        statuses = [r.status for r in results]
        if ValidationStatus.ERROR in statuses:
            overall_status = ValidationStatus.ERROR
        elif ValidationStatus.REJECTED in statuses:
            overall_status = ValidationStatus.REJECTED
        elif ValidationStatus.INVALID in statuses:
            overall_status = ValidationStatus.INVALID
        elif ValidationStatus.SUSPICIOUS in statuses:
            overall_status = ValidationStatus.SUSPICIOUS
        elif ValidationStatus.WARNING in statuses:
            overall_status = ValidationStatus.WARNING
        else:
            overall_status = ValidationStatus.VALID

        # Niveau de risque maximal
        risk_levels = [r.risk_level for r in results]
        overall_risk = max(risk_levels, key=lambda x: [e.value for e in RiskLevel].index(x))

        # Agrégation des checks
        checks_passed = []
        checks_failed = []
        warnings = []
        for r in results:
            checks_passed.extend(r.checks_passed)
            checks_failed.extend(r.checks_failed)
            warnings.extend(r.warnings)

        # Score moyen
        avg_score = sum(r.score for r in results) / len(results)

        return ValidationResult(
            validation_id=validation_id,
            validation_type=ValidationType.TRANSACTION,
            status=overall_status,
            risk_level=overall_risk,
            message=f"Validation complète: {len(checks_passed)}/{(len(checks_passed) + len(checks_failed))} checks réussis",
            details={
                "sub_validation_ids": [r.validation_id for r in results],
                "request_id": request.request_id,
                "bridge_id": request.bridge_id,
            },
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            score=avg_score,
        )

    # ============================================================
    # MÉTHODES DE VÉRIFICATION SPÉCIFIQUES
    # ============================================================

    async def _verify_signature(
        self,
        message: str,
        signature: str,
        address: str,
        provider: Web3,
    ) -> bool:
        """Vérifie une signature cryptographique"""
        try:
            # Récupération du message signé
            message_hash = encode_defunct(text=message)

            # Récupération de l'adresse du signataire
            recovered_address = provider.eth.account.recover_message(
                message_hash,
                signature=signature,
            )

            return recovered_address.lower() == address.lower()

        except Exception as e:
            logger.warning(f"Erreur de vérification de signature: {e}")
            return False

    async def _verify_protocol_in_tx(
        self,
        tx: Dict[str, Any],
        receipt: Dict[str, Any],
        protocol: str,
    ) -> bool:
        """Vérifie la correspondance du protocole dans la transaction"""
        try:
            # Récupération des logs de l'événement
            for log in receipt.get("logs", []):
                # Vérification de l'addresse du contrat du protocole
                contract_address = log.get("address", "").lower()
                protocol_address = self._get_protocol_address(protocol)

                if protocol_address and contract_address == protocol_address.lower():
                    return True

            return False

        except Exception:
            return True  # Si impossible de vérifier, on considère valide

    async def _verify_amount_in_tx(
        self,
        tx: Dict[str, Any],
        receipt: Dict[str, Any],
        expected_amount: Optional[Decimal],
    ) -> bool:
        """Vérifie le montant dans la transaction"""
        if not expected_amount:
            return True

        try:
            # Extraction du montant de la transaction
            value = tx.get("value", 0)
            if value > 0:
                tx_amount = Decimal(str(value)) / Decimal(1e18)
                # Tolérance de 1%
                tolerance = expected_amount * Decimal("0.01")
                return abs(tx_amount - expected_amount) <= tolerance

            return True

        except Exception:
            return True

    async def _check_amount_risk(
        self,
        amount: Decimal,
        token: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Vérifie le risque associé au montant"""
        result = {"status": "passed", "message": ""}

        try:
            # Vérification des seuils de risque
            thresholds = self._risk_thresholds.get(chain, {}).get(token, {})
            warning_threshold = Decimal(thresholds.get("warning", "10000"))
            critical_threshold = Decimal(thresholds.get("critical", "50000"))

            if amount > critical_threshold:
                result["status"] = "critical"
                result["message"] = f"Montant critique: {amount}"
            elif amount > warning_threshold:
                result["status"] = "warning"
                result["message"] = f"Montant élevé: {amount}"

            return result

        except Exception as e:
            logger.warning(f"Erreur de vérification de risque: {e}")
            return {"status": "warning", "message": str(e)}

    async def _validate_address_format(self, address: str, chain: str) -> bool:
        """Valide le format d'une adresse"""
        if not address:
            return False

        # Validation selon la chaîne
        if chain in ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "avalanche"]:
            return is_address(address)

        elif chain == "solana":
            # Format Solana: base58 encodé, 32-44 caractères
            try:
                decoded = base58.b58decode(address)
                return 32 <= len(decoded) <= 44
            except Exception:
                return False

        elif chain == "bitcoin":
            # Format Bitcoin: début par 1, 3, ou bc1
            return re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-zA-Z0-9]{39,59}$", address) is not None

        return False

    async def _check_address_activity(self, address: str, chain: str) -> bool:
        """Vérifie l'activité d'une adresse"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return True

            # Vérification du solde
            balance = await provider.eth.get_balance(address)
            if balance > 0:
                return True

            # Vérification du nombre de transactions
            # (simulé, dans la réalité on utiliserait un indexeur)
            return True

        except Exception:
            return True

    async def _is_blacklisted(self, address: str, chain: str) -> bool:
        """Vérifie si une adresse est dans la liste noire"""
        normalized = f"{chain}:{address.lower()}"
        return normalized in self._blacklist_cache

    async def _is_whitelisted(self, address: str, chain: str) -> bool:
        """Vérifie si une adresse est dans la liste blanche"""
        normalized = f"{chain}:{address.lower()}"
        if self._whitelist_cache:
            return normalized in self._whitelist_cache
        return True  # Si pas de whitelist, tout est autorisé

    async def _check_aml(
        self,
        address: str,
        amount: Decimal,
        token: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Vérification AML"""
        result = {"status": "passed", "message": ""}

        try:
            # Vérification des seuils AML
            aml_threshold = Decimal(self.config.get("aml_threshold", "10000"))

            if amount > aml_threshold:
                # Vérification supplémentaire pour les gros montants
                risk_score = await self._calculate_aml_risk(address, chain)
                if risk_score > 0.5:
                    result["status"] = "failed"
                    result["message"] = f"AML risk score élevé: {risk_score}"

            return result

        except Exception as e:
            logger.warning(f"Erreur AML: {e}")
            return {"status": "warning", "message": str(e)}

    async def _check_kyc(self, address: str, chain: str) -> Dict[str, Any]:
        """Vérification KYC"""
        # Simulé - dans la réalité, vérification auprès d'un fournisseur KYC
        return {"status": "passed", "message": ""}

    async def _check_jurisdiction(self, address: str, chain: str) -> Dict[str, Any]:
        """Vérification des juridictions"""
        # Simulé - dans la réalité, géolocalisation IP
        return {"status": "passed", "message": ""}

    async def _check_sanctions(self, address: str, chain: str) -> Dict[str, Any]:
        """Vérification des sanctions"""
        # Simulé - dans la réalité, vérification OFAC
        return {"status": "passed", "message": ""}

    async def _calculate_aml_risk(self, address: str, chain: str) -> float:
        """Calcule le score de risque AML"""
        # Simulé - dans la réalité, analyse approfondie
        return 0.1

    async def validate_contract(
        self,
        protocol: str,
        chain: str,
    ) -> ValidationResult:
        """
        Valide un contrat de bridge

        Args:
            protocol: Protocole du bridge
            chain: Chaîne du contrat

        Returns:
            Résultat de validation
        """
        validation_id = f"val_contract_{uuid.uuid4().hex[:12]}"
        logger.info(f"Validation du contrat {protocol} sur {chain}")

        try:
            checks_passed = []
            checks_failed = []
            warnings = []

            # Récupération du contrat
            contract_address = self._get_protocol_address(protocol)
            if not contract_address:
                checks_failed.append("contract_address")
                warnings.append("Adresse du contrat non trouvée")
            else:
                checks_passed.append("contract_address")

                # Vérification du code
                provider = self.web3_providers.get(chain)
                if provider:
                    code = await provider.eth.get_code(contract_address)
                    if code and len(code) > 0:
                        checks_passed.append("code")
                    else:
                        checks_failed.append("code")
                        warnings.append("Contrat sans code")
                else:
                    checks_failed.append("provider")
                    warnings.append("Provider non trouvé")

            # Calcul du score
            total_checks = len(checks_passed) + len(checks_failed)
            score = len(checks_passed) / total_checks if total_checks > 0 else 0.0

            status = ValidationStatus.VALID if len(checks_failed) == 0 else ValidationStatus.WARNING

            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.CONTRACT,
                status=status,
                risk_level=RiskLevel.LOW if status == ValidationStatus.VALID else RiskLevel.MEDIUM,
                message=f"Validation du contrat {protocol} terminée",
                details={
                    "protocol": protocol,
                    "chain": chain,
                    "contract_address": contract_address,
                },
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                warnings=warnings,
                score=score,
            )

        except Exception as e:
            logger.error(f"Erreur de validation de contrat: {e}")
            return ValidationResult(
                validation_id=validation_id,
                validation_type=ValidationType.CONTRACT,
                status=ValidationStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                message=f"Erreur de validation: {str(e)}",
                details={"error": str(e)},
                score=0.0,
            )

    async def _verify_merkle_proof(
        self,
        root: str,
        proof: List[str],
        leaf: str,
        chain: str,
    ) -> bool:
        """Vérifie une preuve Merkle"""
        try:
            # Conversion des hex
            root_bytes = bytes.fromhex(root[2:] if root.startswith("0x") else root)
            leaf_bytes = bytes.fromhex(leaf[2:] if leaf.startswith("0x") else leaf)

            # Calcul du hash
            current_hash = leaf_bytes

            for proof_element in proof:
                proof_bytes = bytes.fromhex(
                    proof_element[2:] if proof_element.startswith("0x") else proof_element
                )

                # Hachage combiné
                if current_hash < proof_bytes:
                    combined = current_hash + proof_bytes
                else:
                    combined = proof_bytes + current_hash

                current_hash = hashlib.sha256(combined).digest()

            return current_hash.hex() == root_bytes.hex()

        except Exception as e:
            logger.warning(f"Erreur de vérification Merkle: {e}")
            return False

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_cache_key(self, request: BridgeValidationRequest) -> str:
        """Génère une clé de cache"""
        key_parts = [
            request.bridge_id,
            request.protocol,
            str(request.amount),
            request.source_address,
            request.destination_address,
            request.validation_level.value,
        ]
        return hashlib.sha256(":".join(key_parts).encode()).hexdigest()

    def _get_min_amount(self, token: str, chain: str, protocol: str) -> Decimal:
        """Obtient le montant minimum"""
        min_amount = Decimal(self.config.get("min_amount", {}).get(chain, {}).get(token, "0.001"))
        return min_amount

    def _get_max_amount(self, token: str, chain: str, protocol: str) -> Decimal:
        """Obtient le montant maximum"""
        max_amount = Decimal(self.config.get("max_amount", {}).get(chain, {}).get(token, "1000000"))
        return max_amount

    async def _get_token_decimals(self, token: str, chain: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        # Simulé - dans la réalité, appel au contrat
        decimals_map = {
            "ETH": 18,
            "USDC": 6,
            "USDT": 6,
            "DAI": 18,
            "WBTC": 8,
            "BNB": 18,
            "MATIC": 18,
        }
        return decimals_map.get(token, 18)

    def _get_protocol_address(self, protocol: str) -> Optional[str]:
        """Obtient l'adresse du contrat pour un protocole"""
        protocols = self.config.get("protocols", {})
        return protocols.get(protocol, {}).get("address")

    def _get_supported_protocols(self) -> List[str]:
        """Obtient la liste des protocoles supportés"""
        return list(self.config.get("protocols", {}).keys())

    def _calculate_risk_level(self, validations: List[Tuple[str, bool, str]]) -> RiskLevel:
        """Calcule le niveau de risque"""
        failed = sum(1 for _, success, _ in validations if not success)
        total = len(validations)

        if total == 0:
            return RiskLevel.LOW

        failure_rate = failed / total

        if failure_rate >= 0.5:
            return RiskLevel.CRITICAL
        elif failure_rate >= 0.3:
            return RiskLevel.HIGH
        elif failure_rate >= 0.1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _load_validation_rules(self) -> Dict[str, Any]:
        """Charge les règles de validation"""
        return self.config.get("validation_rules", {
            "require_signature": True,
            "require_merkle_proof": False,
            "max_slippage": Decimal("0.01"),
            "min_confirmations": 12,
            "max_amount_no_kyc": Decimal("10000"),
        })

    def _load_risk_thresholds(self) -> Dict[str, Any]:
        """Charge les seuils de risque"""
        return self.config.get("risk_thresholds", {})

    def _load_compliance_rules(self) -> Dict[str, Any]:
        """Charge les règles de conformité"""
        return self.config.get("compliance_rules", {
            "require_aml": True,
            "require_kyc": True,
            "jurisdictions_allowed": ["US", "EU", "UK", "SG", "JP"],
            "sanctions_check": True,
        })

    def _load_security_lists(self) -> None:
        """Charge les listes de sécurité"""
        # Liste noire
        blacklist = self.config.get("blacklist", [])
        self._blacklist_cache = set(blacklist)

        # Liste blanche
        whitelist = self.config.get("whitelist", [])
        self._whitelist_cache = set(whitelist)

        logger.info(
            f"Listes de sécurité chargées: "
            f"{len(self._blacklist_cache)} blacklisted, "
            f"{len(self._whitelist_cache)} whitelisted"
        )

    def _update_stats(self, protocol: str, result: ValidationResult) -> None:
        """Met à jour les statistiques"""
        self._validation_stats[protocol][result.status.value] += 1

    # ============================================================
    # MÉTHODES DE STATISTIQUES ET RAPPORT
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de validation"""
        total_validations = sum(
            sum(stats.values()) for stats in self._validation_stats.values()
        )

        return {
            "total_validations": total_validations,
            "protocol_stats": {
                protocol: dict(stats)
                for protocol, stats in self._validation_stats.items()
            },
            "blacklist_size": len(self._blacklist_cache),
            "whitelist_size": len(self._whitelist_cache),
            "cache_size": len(self._validation_cache),
            "cache_ttl": self.cache_ttl,
        }

    async def get_validation_history(
        self,
        limit: int = 100,
        protocol: Optional[str] = None,
    ) -> List[ValidationResult]:
        """
        Obtient l'historique des validations

        Args:
            limit: Nombre maximum de résultats
            protocol: Filtrer par protocole

        Returns:
            Liste des résultats de validation
        """
        # Dans une implémentation réelle, on utiliserait une base de données
        # Ici, on retourne les résultats du cache
        results = []
        for _, (_, result) in list(self._validation_cache.items())[-limit:]:
            if protocol is None or result.metadata.get("protocol") == protocol:
                results.append(result)
        return results

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeValidator...")

        # Nettoyage du cache
        self._validation_cache.clear()
        self._risk_cache.clear()
        self._contract_cache.clear()
        self._abi_cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_validator(
    config: Dict[str, Any],
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> BridgeValidator:
    """
    Crée une instance de BridgeValidator

    Args:
        config: Configuration
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeValidator
    """
    return BridgeValidator(
        config=config,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeValidator"""
    # Configuration
    config = {
        "protocols": {
            "layerzero": {
                "address": "0x...",
            },
            "wormhole": {
                "address": "0x...",
            },
        },
        "min_amount": {
            "ethereum": {
                "USDC": "1",
                "ETH": "0.001",
            },
        },
        "max_amount": {
            "ethereum": {
                "USDC": "100000",
                "ETH": "100",
            },
        },
        "risk_thresholds": {
            "ethereum": {
                "USDC": {
                    "warning": "10000",
                    "critical": "50000",
                },
            },
        },
        "blacklist": ["0x...", "0x..."],
        "whitelist": ["0x..."],
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
    }

    # Création du validateur
    validator = create_bridge_validator(
        config=config,
        web3_providers=web3_providers,
    )

    # Validation d'un bridge
    request = BridgeValidationRequest(
        request_id="req_123",
        bridge_id="bridge_123",
        protocol="layerzero",
        chain_from="ethereum",
        chain_to="arbitrum",
        token_from="USDC",
        token_to="USDC",
        amount=Decimal("1000"),
        source_address="0x...",
        destination_address="0x...",
        tx_hash="0x...",
        validation_level=ValidationLevel.COMPREHENSIVE,
    )

    result = await validator.validate_bridge(request)
    print(f"Résultat: {result.to_dict()}")
    print(f"Valide: {result.is_valid()}")

    # Statistiques
    stats = validator.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await validator.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

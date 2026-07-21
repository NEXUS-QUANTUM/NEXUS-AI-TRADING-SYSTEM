"""
NEXUS AI TRADING SYSTEM - HEDGE BOT COMPLIANCE MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion de la conformité pour le Hedge Bot.
Gestion des règles de conformité, KYC, AML, et reporting réglementaire.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import phonenumbers
from cryptography.fernet import Fernet

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    is_valid_uuid,
    is_valid_address
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class ComplianceStatus(Enum):
    """Statuts de conformité."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVIEW = "review"
    APPROVED = "approved"


class KYCLevel(Enum):
    """Niveaux KYC."""
    NONE = "none"
    LEVEL_1 = "level_1"  # Basic
    LEVEL_2 = "level_2"  # Enhanced
    LEVEL_3 = "level_3"  # Full
    INSTITUTIONAL = "institutional"
    CORPORATE = "corporate"


class AMLStatus(Enum):
    """Statuts AML."""
    CLEAR = "clear"
    FLAGGED = "flagged"
    INVESTIGATING = "investigating"
    BLOCKED = "blocked"
    REPORTED = "reported"


class SanctionList(Enum):
    """Listes de sanctions."""
    OFAC = "ofac"
    UN = "un"
    EU = "eu"
    UK = "uk"
    INTERPOL = "interpol"
    CUSTOM = "custom"


@dataclass
class ComplianceRule:
    """Règle de conformité."""
    rule_id: UUID
    name: str
    description: str
    category: str
    condition: str
    action: str
    severity: str  # low, medium, high, critical
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "rule_id": str(self.rule_id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "condition": self.condition,
            "action": self.action,
            "severity": self.severity,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class KYCRecord:
    """Enregistrement KYC."""
    record_id: UUID
    user_id: UUID
    level: KYCLevel
    status: ComplianceStatus
    documents: List[Dict[str, Any]]
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "record_id": str(self.record_id),
            "user_id": str(self.user_id),
            "level": self.level.value,
            "status": self.status.value,
            "documents": self.documents,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class AMLRecord:
    """Enregistrement AML."""
    record_id: UUID
    user_id: UUID
    status: AMLStatus
    flags: List[str]
    sanctions: List[SanctionList]
    risk_score: float
    reviewed_at: Optional[datetime] = None
    reported_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "record_id": str(self.record_id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "flags": self.flags,
            "sanctions": [s.value for s in self.sanctions],
            "risk_score": self.risk_score,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class ComplianceReport:
    """Rapport de conformité."""
    report_id: UUID
    user_id: UUID
    report_type: str
    status: ComplianceStatus
    content: Dict[str, Any]
    generated_at: datetime
    reviewed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "report_type": self.report_type,
            "status": self.status.value,
            "content": self.content,
            "generated_at": self.generated_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE COMPLIANCE MANAGER
# ============================================================================

class ComplianceManager:
    """
    Gestionnaire de conformité avancé.
    """

    # Niveaux KYC requis par type d'opération
    KYC_REQUIREMENTS = {
        "trading": KYCLevel.LEVEL_1,
        "withdrawal": KYCLevel.LEVEL_2,
        "deposit": KYCLevel.LEVEL_1,
        "staking": KYCLevel.LEVEL_2,
        "lending": KYCLevel.LEVEL_2,
        "margin": KYCLevel.LEVEL_3,
        "institutional": KYCLevel.INSTITUTIONAL
    }

    # Délais d'expiration KYC
    KYC_EXPIRATION = {
        KYCLevel.LEVEL_1: 365,
        KYCLevel.LEVEL_2: 180,
        KYCLevel.LEVEL_3: 90,
        KYCLevel.INSTITUTIONAL: 365,
        KYCLevel.CORPORATE: 365
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        encryption_key: Optional[str] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de conformité.

        Args:
            redis_client: Client Redis pour le cache
            encryption_key: Clé de chiffrement
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.encryption_key = encryption_key
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Chiffrement
        self._fernet = None
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())
        
        # Cache
        self._rule_cache: Dict[UUID, ComplianceRule] = {}
        self._kyc_cache: Dict[UUID, KYCRecord] = {}
        self._aml_cache: Dict[UUID, AMLRecord] = {}
        self._report_cache: Dict[UUID, ComplianceReport] = {}
        
        # Règles par défaut
        self._default_rules = self._init_default_rules()
        
        # Métriques
        self._metrics = {
            "total_kyc": 0,
            "total_aml": 0,
            "total_reports": 0,
            "verified_kyc": 0,
            "rejected_kyc": 0,
            "aml_flags": 0,
            "by_level": {},
            "by_status": {}
        }

        logger.info("ComplianceManager initialisé avec succès")

    def _init_default_rules(self) -> List[ComplianceRule]:
        """
        Initialise les règles de conformité par défaut.

        Returns:
            Liste des règles
        """
        rules = [
            ComplianceRule(
                rule_id=uuid4(),
                name="KYC Required",
                description="Tout utilisateur doit avoir un KYC valide",
                category="kyc",
                condition="user.kyc.status != 'verified'",
                action="block",
                severity="high"
            ),
            ComplianceRule(
                rule_id=uuid4(),
                name="AML Check",
                description="Vérification AML pour toutes les transactions",
                category="aml",
                condition="transaction.amount > 10000",
                action="review",
                severity="medium"
            ),
            ComplianceRule(
                rule_id=uuid4(),
                name="Sanctions Check",
                description="Vérification des listes de sanctions",
                category="sanctions",
                condition="user.address in sanctions_list",
                action="block",
                severity="critical"
            ),
            ComplianceRule(
                rule_id=uuid4(),
                name="Daily Limit",
                description="Limite quotidienne de transactions",
                category="limits",
                condition="user.daily_volume > 100000",
                action="alert",
                severity="medium"
            )
        ]
        
        for rule in rules:
            self._rule_cache[rule.rule_id] = rule
        
        return rules

    # ========================================================================
    # GESTION KYC
    # ========================================================================

    async def submit_kyc(
        self,
        user_id: UUID,
        level: KYCLevel,
        documents: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> KYCRecord:
        """
        Soumet une demande KYC.

        Args:
            user_id: ID de l'utilisateur
            level: Niveau KYC
            documents: Documents
            metadata: Métadonnées

        Returns:
            Enregistrement KYC
        """
        try:
            record_id = uuid4()
            now = datetime.now()
            
            expiration_days = self.KYC_EXPIRATION.get(level, 180)
            expires_at = now + timedelta(days=expiration_days)

            # Chiffrement des documents
            if self._fernet:
                documents = self._encrypt_documents(documents)

            record = KYCRecord(
                record_id=record_id,
                user_id=user_id,
                level=level,
                status=ComplianceStatus.PENDING,
                documents=documents,
                expires_at=expires_at,
                metadata=metadata or {}
            )

            self._kyc_cache[record_id] = record
            self._metrics["total_kyc"] += 1

            level_key = level.value
            if level_key not in self._metrics["by_level"]:
                self._metrics["by_level"][level_key] = 0
            self._metrics["by_level"][level_key] += 1

            return record

        except Exception as e:
            logger.error(f"Erreur de soumission KYC: {e}")
            raise

    async def verify_kyc(
        self,
        record_id: UUID,
        status: ComplianceStatus,
        notes: Optional[str] = None
    ) -> bool:
        """
        Vérifie une demande KYC.

        Args:
            record_id: ID de l'enregistrement
            status: Statut de vérification
            notes: Notes

        Returns:
            True si vérifié
        """
        try:
            record = self._kyc_cache.get(record_id)
            if not record:
                return False

            record.status = status
            record.updated_at = datetime.now()

            if status == ComplianceStatus.VERIFIED:
                record.verified_at = datetime.now()
                self._metrics["verified_kyc"] += 1
            elif status == ComplianceStatus.REJECTED:
                self._metrics["rejected_kyc"] += 1

            status_key = status.value
            if status_key not in self._metrics["by_status"]:
                self._metrics["by_status"][status_key] = 0
            self._metrics["by_status"][status_key] += 1

            return True

        except Exception as e:
            logger.error(f"Erreur de vérification KYC: {e}")
            return False

    async def get_kyc_status(
        self,
        user_id: UUID
    ) -> Optional[KYCRecord]:
        """
        Récupère le statut KYC d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Enregistrement KYC ou None
        """
        for record in self._kyc_cache.values():
            if record.user_id == user_id:
                return record
        return None

    # ========================================================================
    # GESTION AML
    # ========================================================================

    async def check_aml(
        self,
        user_id: UUID,
        transaction: Dict[str, Any]
    ) -> AMLRecord:
        """
        Vérifie une transaction AML.

        Args:
            user_id: ID de l'utilisateur
            transaction: Données de la transaction

        Returns:
            Enregistrement AML
        """
        try:
            record_id = uuid4()
            now = datetime.now()
            
            # Calcul du score de risque
            risk_score = await self._calculate_risk_score(user_id, transaction)
            
            # Vérification des sanctions
            sanctions = await self._check_sanctions(user_id)
            
            # Détermination du statut
            status = AMLStatus.CLEAR
            flags = []

            if risk_score > 0.8:
                status = AMLStatus.BLOCKED
                flags.append("high_risk")
            elif risk_score > 0.6:
                status = AMLStatus.FLAGGED
                flags.append("medium_risk")
            elif sanctions:
                status = AMLStatus.BLOCKED
                flags.append("sanctions_match")

            if transaction.get("amount", 0) > 10000:
                flags.append("large_transaction")

            record = AMLRecord(
                record_id=record_id,
                user_id=user_id,
                status=status,
                flags=flags,
                sanctions=sanctions,
                risk_score=risk_score,
                metadata={"transaction": transaction}
            )

            self._aml_cache[record_id] = record
            self._metrics["total_aml"] += 1

            if flags:
                self._metrics["aml_flags"] += 1

            return record

        except Exception as e:
            logger.error(f"Erreur de vérification AML: {e}")
            raise

    async def _calculate_risk_score(
        self,
        user_id: UUID,
        transaction: Dict[str, Any]
    ) -> float:
        """
        Calcule le score de risque AML.

        Args:
            user_id: ID de l'utilisateur
            transaction: Données de la transaction

        Returns:
            Score de risque
        """
        risk_score = 0.0

        # Facteurs de risque
        if transaction.get("amount", 0) > 10000:
            risk_score += 0.3
        if transaction.get("amount", 0) > 50000:
            risk_score += 0.3
        if transaction.get("new_user", False):
            risk_score += 0.2
        if transaction.get("high_risk_country", False):
            risk_score += 0.2
        if transaction.get("multiple_transactions", False):
            risk_score += 0.1

        return min(risk_score, 1.0)

    async def _check_sanctions(
        self,
        user_id: UUID
    ) -> List[SanctionList]:
        """
        Vérifie les listes de sanctions.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste des sanctions
        """
        # Simulation de vérification
        sanctions = []
        
        # Récupération des listes
        for sanction_list in SanctionList:
            # Vérification (simulée)
            if await self._check_sanction_list(user_id, sanction_list):
                sanctions.append(sanction_list)

        return sanctions

    async def _check_sanction_list(
        self,
        user_id: UUID,
        sanction_list: SanctionList
    ) -> bool:
        """
        Vérifie une liste de sanctions spécifique.

        Args:
            user_id: ID de l'utilisateur
            sanction_list: Liste de sanctions

        Returns:
            True si match
        """
        # Simulation
        return False

    # ========================================================================
    # RAPPORTS DE CONFORMITÉ
    # ========================================================================

    async def generate_report(
        self,
        user_id: UUID,
        report_type: str = "kyc_aml",
        metadata: Optional[Dict] = None
    ) -> ComplianceReport:
        """
        Génère un rapport de conformité.

        Args:
            user_id: ID de l'utilisateur
            report_type: Type de rapport
            metadata: Métadonnées

        Returns:
            Rapport de conformité
        """
        try:
            report_id = uuid4()
            now = datetime.now()

            content = {
                "user_id": str(user_id),
                "report_type": report_type,
                "generated_at": now.isoformat(),
                "kyc_status": await self.get_kyc_status(user_id),
                "aml_records": [
                    r.to_dict() for r in self._aml_cache.values()
                    if r.user_id == user_id
                ]
            }

            report = ComplianceReport(
                report_id=report_id,
                user_id=user_id,
                report_type=report_type,
                status=ComplianceStatus.PENDING,
                content=content,
                generated_at=now,
                metadata=metadata or {}
            )

            self._report_cache[report_id] = report
            self._metrics["total_reports"] += 1

            return report

        except Exception as e:
            logger.error(f"Erreur de génération de rapport: {e}")
            raise

    # ========================================================================
    # VÉRIFICATION DE CONFORMITÉ
    # ========================================================================

    async def check_compliance(
        self,
        user_id: UUID,
        action: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Vérifie la conformité pour une action.

        Args:
            user_id: ID de l'utilisateur
            action: Action
            data: Données

        Returns:
            Résultat de la vérification
        """
        try:
            result = {
                "status": "ok",
                "message": "Action conforme",
                "checks": []
            }

            # Vérification KYC
            kyc_status = await self.get_kyc_status(user_id)
            required_level = self.KYC_REQUIREMENTS.get(action, KYCLevel.LEVEL_1)

            if not kyc_status or kyc_status.status != ComplianceStatus.VERIFIED:
                result["status"] = "failed"
                result["message"] = "KYC requis"
                result["checks"].append({
                    "type": "kyc",
                    "status": "failed",
                    "required_level": required_level.value
                })
            elif kyc_status.level.value < required_level.value:
                result["status"] = "failed"
                result["message"] = f"Niveau KYC insuffisant (requis: {required_level.value})"
                result["checks"].append({
                    "type": "kyc",
                    "status": "failed",
                    "current_level": kyc_status.level.value,
                    "required_level": required_level.value
                })

            # Vérification AML
            aml_check = await self.check_aml(user_id, data)
            if aml_check.status in [AMLStatus.FLAGGED, AMLStatus.BLOCKED]:
                result["status"] = "failed"
                result["message"] = "Alerte AML"
                result["checks"].append({
                    "type": "aml",
                    "status": aml_check.status.value,
                    "flags": aml_check.flags
                })

            # Vérification des règles
            for rule in self._rule_cache.values():
                if not rule.enabled:
                    continue

                if await self._evaluate_rule(rule, user_id, data):
                    result["status"] = "failed"
                    result["message"] = f"Règle de conformité violée: {rule.name}"
                    result["checks"].append({
                        "type": "rule",
                        "rule_id": str(rule.rule_id),
                        "rule_name": rule.name,
                        "severity": rule.severity
                    })

            return result

        except Exception as e:
            logger.error(f"Erreur de vérification de conformité: {e}")
            return {
                "status": "error",
                "message": str(e),
                "checks": []
            }

    async def _evaluate_rule(
        self,
        rule: ComplianceRule,
        user_id: UUID,
        data: Dict[str, Any]
    ) -> bool:
        """
        Évalue une règle de conformité.

        Args:
            rule: Règle
            user_id: ID de l'utilisateur
            data: Données

        Returns:
            True si la règle est violée
        """
        try:
            # Évaluation des conditions (simplifiée)
            # En production, utiliser un moteur de règles
            if rule.condition == "user.kyc.status != 'verified'":
                kyc = await self.get_kyc_status(user_id)
                return not kyc or kyc.status != ComplianceStatus.VERIFIED
            
            elif rule.condition == "transaction.amount > 10000":
                return data.get("amount", 0) > 10000
            
            elif rule.condition == "user.address in sanctions_list":
                sanctions = await self._check_sanctions(user_id)
                return len(sanctions) > 0
            
            elif rule.condition == "user.daily_volume > 100000":
                # Simulation
                return data.get("daily_volume", 0) > 100000

            return False

        except Exception as e:
            logger.error(f"Erreur d'évaluation de règle: {e}")
            return True

    # ========================================================================
    # MÉTHODES DE CHIFFREMENT
    # ========================================================================

    def _encrypt_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Chiffre les documents.

        Args:
            documents: Documents

        Returns:
            Documents chiffrés
        """
        if not self._fernet:
            return documents

        encrypted_docs = []
        for doc in documents:
            doc_copy = doc.copy()
            if "content" in doc_copy:
                content = json.dumps(doc_copy["content"])
                doc_copy["content"] = self._fernet.encrypt(content.encode()).decode()
            encrypted_docs.append(doc_copy)

        return encrypted_docs

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_rule(
        self,
        rule_id: UUID
    ) -> Optional[ComplianceRule]:
        """
        Récupère une règle.

        Args:
            rule_id: ID de la règle

        Returns:
            Règle ou None
        """
        return self._rule_cache.get(rule_id)

    async def get_aml_record(
        self,
        record_id: UUID
    ) -> Optional[AMLRecord]:
        """
        Récupère un enregistrement AML.

        Args:
            record_id: ID de l'enregistrement

        Returns:
            Enregistrement AML ou None
        """
        return self._aml_cache.get(record_id)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_kyc": self._metrics["total_kyc"],
                "total_aml": self._metrics["total_aml"],
                "total_reports": self._metrics["total_reports"],
                "verified_kyc": self._metrics["verified_kyc"],
                "rejected_kyc": self._metrics["rejected_kyc"],
                "aml_flags": self._metrics["aml_flags"],
                "by_level": self._metrics["by_level"],
                "by_status": self._metrics["by_status"],
                "cached_rules": len(self._rule_cache),
                "cached_kyc": len(self._kyc_cache),
                "cached_aml": len(self._aml_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de ComplianceManager...")
        self._rule_cache.clear()
        self._kyc_cache.clear()
        self._aml_cache.clear()
        self._report_cache.clear()
        logger.info("ComplianceManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_compliance_manager(
    redis_url: str = "redis://localhost:6379/0",
    encryption_key: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> ComplianceManager:
    """
    Crée une instance de ComplianceManager.

    Args:
        redis_url: URL de connexion Redis
        encryption_key: Clé de chiffrement
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de ComplianceManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ComplianceManager(
        redis_client=redis_client,
        encryption_key=encryption_key,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ComplianceStatus",
    "KYCLevel",
    "AMLStatus",
    "SanctionList",
    "ComplianceRule",
    "KYCRecord",
    "AMLRecord",
    "ComplianceReport",
    "ComplianceManager",
    "create_compliance_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du ComplianceManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT COMPLIANCE MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    compliance = create_compliance_manager()

    print(f"\n✅ ComplianceManager initialisé")

    # Soumission KYC
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📋 Soumission KYC...")
    
    kyc = await compliance.submit_kyc(
        user_id=user_id,
        level=KYCLevel.LEVEL_2,
        documents=[
            {
                "type": "id_card",
                "content": {"number": "123456789"},
                "status": "uploaded"
            },
            {
                "type": "proof_of_address",
                "content": {"address": "123 Main St"},
                "status": "uploaded"
            }
        ],
        metadata={"source": "web"}
    )

    print(f"   ID: {kyc.record_id}")
    print(f"   Niveau: {kyc.level.value}")
    print(f"   Statut: {kyc.status.value}")

    # Vérification KYC
    print(f"\n✅ Vérification KYC...")
    await compliance.verify_kyc(
        record_id=kyc.record_id,
        status=ComplianceStatus.VERIFIED,
        notes="Documents valides"
    )

    updated_kyc = await compliance.get_kyc_status(user_id)
    print(f"   Statut: {updated_kyc.status.value}")

    # Vérification AML
    print(f"\n🔍 Vérification AML...")
    transaction = {
        "amount": 15000,
        "new_user": False,
        "high_risk_country": False
    }

    aml = await compliance.check_aml(user_id, transaction)
    print(f"   Statut: {aml.status.value}")
    print(f"   Score de risque: {aml.risk_score:.2f}")
    print(f"   Flags: {aml.flags}")

    # Vérification de conformité
    print(f"\n✅ Vérification de conformité...")
    result = await compliance.check_compliance(
        user_id=user_id,
        action="trading",
        data={"amount": 5000}
    )

    print(f"   Statut: {result['status']}")
    print(f"   Message: {result['message']}")

    # Rapport de conformité
    print(f"\n📊 Génération du rapport...")
    report = await compliance.generate_report(
        user_id=user_id,
        report_type="kyc_aml"
    )

    print(f"   ID: {report.report_id}")
    print(f"   Type: {report.report_type}")

    # Santé du service
    health = await compliance.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   KYC: {health['total_kyc']}")
    print(f"   AML: {health['total_aml']}")
    print(f"   AML Flags: {health['aml_flags']}")

    # Fermeture
    await compliance.close()

    print("\n" + "=" * 60)
    print("ComplianceManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

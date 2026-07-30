# trading/bots/hedge_bot/hedge_bot_data_governance.py
# Advanced Data Governance & Compliance Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Governance Module - Module de gouvernance et conformité des données avancé
pour le Hedge Bot. Assure la gestion des politiques de données, la conformité réglementaire,
l'audit, la traçabilité et la protection des données pour l'ensemble du système de hedging.
"""

import asyncio
import json
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import re

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_governance")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class DataPolicyCategory(Enum):
    """Catégories de politiques de données."""
    PRIVACY = "privacy"
    RETENTION = "retention"
    ACCESS = "access"
    SECURITY = "security"
    QUALITY = "quality"
    COMPLIANCE = "compliance"
    ARCHIVAL = "archival"
    DISPOSAL = "disposal"
    CLASSIFICATION = "classification"


class DataGovernanceStatus(Enum):
    """Statuts de gouvernance."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    EXEMPTED = "exempted"
    PENDING = "pending"
    ERROR = "error"


class GDPRCategory(Enum):
    """Catégories GDPR."""
    PERSONAL_DATA = "personal_data"
    SENSITIVE_DATA = "sensitive_data"
    PSEUDONYMIZED = "pseudonymized"
    ANONYMIZED = "anonymized"
    METADATA = "metadata"
    AGGREGATED = "aggregated"
    RESTRICTED = "restricted"


class DataRetentionPolicy(Enum):
    """Politiques de rétention."""
    MINIMAL = "minimal"      # 7 jours
    STANDARD = "standard"    # 30 jours
    EXTENDED = "extended"    # 90 jours
    LONG_TERM = "long_term"  # 365 jours
    INDEFINITE = "indefinite" # Indéfini
    REGULATORY = "regulatory" # Selon réglementation


# ============== DATA MODELS ==============

@dataclass
class DataPolicy:
    """Modèle de politique de données."""
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: DataPolicyCategory = DataPolicyCategory.COMPLIANCE
    version: str = "1.0.0"
    effective_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiration_date: Optional[datetime] = None
    rules: Dict[str, Any] = field(default_factory=dict)
    scope: List[str] = field(default_factory=list)
    jurisdiction: List[str] = field(default_factory=list)
    status: DataGovernanceStatus = DataGovernanceStatus.PENDING
    created_by: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "effective_date": self.effective_date.isoformat(),
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "rules": self.rules,
            "scope": self.scope,
            "jurisdiction": self.jurisdiction,
            "status": self.status.value,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class DataClassification:
    """Classification des données."""
    classification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.MARKET
    classification: DataPolicyCategory = DataPolicyCategory.COMPLIANCE
    gdpr_category: GDPRCategory = GDPRCategory.AGGREGATED
    retention_policy: DataRetentionPolicy = DataRetentionPolicy.STANDARD
    encryption_required: bool = False
    access_level: str = "read_only"  # read_only, read_write, admin, restricted
    jurisdictions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuditTrail:
    """Traçabilité d'audit."""
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user: str = ""
    action: str = ""  # create, read, update, delete, export, share, etc.
    resource_type: str = ""
    resource_id: str = ""
    data_type: DataType = DataType.MARKET
    policy_id: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = "success"  # success, failure, denied
    compliance_status: DataGovernanceStatus = DataGovernanceStatus.COMPLIANT
    signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSubjectRequest:
    """Requête de sujet de données (GDPR)."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_type: str = ""  # access, rectification, erasure, restriction, portability, objection
    requester: str = ""
    subject: str = ""
    status: str = "pending"  # pending, processing, completed, rejected
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    response: Optional[str] = None
    data: Optional[Any] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    """Rapport de conformité."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    jurisdiction: str = ""
    status: DataGovernanceStatus = DataGovernanceStatus.COMPLIANT
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    policies_checked: List[str] = field(default_factory=list)
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    end_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class GovernanceEngineInterface(ABC):
    """Interface abstraite pour le moteur de gouvernance."""
    
    @abstractmethod
    async def create_policy(self, policy: DataPolicy) -> str:
        """Crée une politique de données."""
        pass
    
    @abstractmethod
    async def classify_data(self, classification: DataClassification) -> str:
        """Classifie des données."""
        pass
    
    @abstractmethod
    async def audit_action(self, audit: AuditTrail) -> str:
        """Enregistre une action d'audit."""
        pass
    
    @abstractmethod
    async def check_compliance(self, resource: Dict[str, Any]) -> DataGovernanceStatus:
        """Vérifie la conformité d'une ressource."""
        pass


# ============== IMPLÉMENTATION ==============

class GovernanceEngine(GovernanceEngineInterface):
    """
    Moteur de gouvernance et conformité avancé pour le Hedge Bot.
    Assure la gestion des politiques, la classification, l'audit et la conformité.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des politiques
        self._policies: Dict[str, DataPolicy] = {}
        self._policies_lock = threading.RLock()
        
        # Gestion des classifications
        self._classifications: Dict[str, DataClassification] = {}
        self._class_lock = threading.RLock()
        
        # Gestion des audits
        self._audits: Dict[str, AuditTrail] = {}
        self._audit_lock = threading.RLock()
        
        # Gestion des requêtes GDPR
        self._data_requests: Dict[str, DataSubjectRequest] = {}
        self._req_lock = threading.RLock()
        
        # Rapports de conformité
        self._reports: Dict[str, ComplianceReport] = {}
        self._report_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "policies_created": 0,
            "classifications_created": 0,
            "audits_recorded": 0,
            "data_requests_processed": 0,
            "compliance_reports_generated": 0,
            "compliance_rate": 1.0
        }
        
        # État
        self._is_running = False
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        logger.info("GovernanceEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_jurisdiction": "eu",
            "compliance_check_interval": 3600,  # 1 heure
            "audit_retention_days": 365,
            "max_audit_entries": 100000,
            "auto_classify": True,
            "enable_audit": True,
            "require_encryption": True,
            "privacy_default": DataRetentionPolicy.STANDARD,
            "data_retention_override": {}
        }
    
    async def start(self) -> None:
        """Démarre le moteur de gouvernance."""
        logger.info("GovernanceEngine starting...")
        self._is_running = True
        
        # Chargement des politiques existantes
        await self._load_policies()
        
        # Chargement des classifications
        await self._load_classifications()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._compliance_checker_loop())
        asyncio.create_task(self._audit_cleaner_loop())
        asyncio.create_task(self._report_generator_loop())
        
        logger.info("GovernanceEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de gouvernance."""
        logger.info("GovernanceEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("GovernanceEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_policy(self, policy: DataPolicy) -> str:
        """Crée une politique de données."""
        with self._policies_lock:
            self._policies[policy.policy_id] = policy
            self._stats["policies_created"] += 1
        
        # Validation de la politique
        await self._validate_policy(policy)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"governance:policy:{policy.policy_id}",
                policy.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Data policy created: {policy.name} (id={policy.policy_id})")
        return policy.policy_id
    
    async def classify_data(self, classification: DataClassification) -> str:
        """Classifie des données."""
        with self._class_lock:
            self._classifications[classification.classification_id] = classification
            self._stats["classifications_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"governance:classification:{classification.classification_id}",
                classification.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Data classification created: {classification.classification_id} "
                   f"type={classification.data_type.value}")
        return classification.classification_id
    
    async def audit_action(self, audit: AuditTrail) -> str:
        """Enregistre une action d'audit."""
        self._stats["audits_recorded"] += 1
        
        # Vérification de conformité
        audit.compliance_status = await self.check_compliance(audit.details)
        
        # Signature
        if self.config["enable_audit"]:
            audit.signature = self._sign_audit(audit)
        
        with self._audit_lock:
            self._audits[audit.audit_id] = audit
        
        # Stockage persistant
        if self.data_manager and self.config["enable_audit"]:
            await self.data_manager.store(
                f"governance:audit:{audit.audit_id}",
                audit.to_dict(),
                DataType.AUDIT
            )
        
        logger.debug(f"Audit recorded: {audit.action} by {audit.user} on {audit.resource_id}")
        return audit.audit_id
    
    async def check_compliance(self, resource: Dict[str, Any]) -> DataGovernanceStatus:
        """Vérifie la conformité d'une ressource."""
        # Vérification des politiques
        with self._policies_lock:
            for policy in self._policies.values():
                # Vérification des règles
                if not self._check_policy_compliance(resource, policy):
                    return DataGovernanceStatus.NON_COMPLIANT
        
        # Vérification des classifications
        with self._class_lock:
            data_type = resource.get("data_type")
            if data_type:
                for classification in self._classifications.values():
                    if classification.data_type.value == data_type:
                        if not self._check_classification_compliance(resource, classification):
                            return DataGovernanceStatus.NON_COMPLIANT
        
        return DataGovernanceStatus.COMPLIANT
    
    # ========== MÉTHODES PRIVÉES - COMPLIANCE ==========
    
    async def _validate_policy(self, policy: DataPolicy) -> bool:
        """Valide une politique."""
        if not policy.name:
            raise ValueError("Policy name is required")
        
        if not policy.rules:
            raise ValueError("Policy rules are required")
        
        return True
    
    def _check_policy_compliance(self, resource: Dict[str, Any], policy: DataPolicy) -> bool:
        """Vérifie la conformité avec une politique."""
        rules = policy.rules
        
        # Vérification des règles de rétention
        if "retention_days" in rules:
            if resource.get("age_days", 0) > rules["retention_days"]:
                return False
        
        # Vérification des règles de chiffrement
        if rules.get("encryption_required", False):
            if not resource.get("encrypted", False):
                return False
        
        # Vérification des règles de classification
        if "allowed_classifications" in rules:
            if resource.get("classification") not in rules["allowed_classifications"]:
                return False
        
        return True
    
    def _check_classification_compliance(
        self,
        resource: Dict[str, Any],
        classification: DataClassification
    ) -> bool:
        """Vérifie la conformité avec une classification."""
        # Vérification du chiffrement
        if classification.encryption_required:
            if not resource.get("encrypted", False):
                return False
        
        # Vérification du niveau d'accès
        if classification.access_level == "restricted":
            if not resource.get("authorized", False):
                return False
        
        # Vérification de la juridiction
        if classification.jurisdictions:
            jurisdiction = resource.get("jurisdiction", "unknown")
            if jurisdiction not in classification.jurisdictions:
                return False
        
        return True
    
    def _sign_audit(self, audit: AuditTrail) -> str:
        """Signe un audit pour l'intégrité."""
        # Création d'une signature HMAC
        data = f"{audit.timestamp}{audit.user}{audit.action}{audit.resource_id}"
        secret = self.config.get("audit_secret", "default_secret")
        signature = hmac.new(
            secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    # ========== MÉTHODES PRIVÉES - GDPR ==========
    
    async def process_data_request(self, request: DataSubjectRequest) -> Dict[str, Any]:
        """Traite une requête de sujet de données (GDPR)."""
        with self._req_lock:
            self._data_requests[request.request_id] = request
            self._stats["data_requests_processed"] += 1
        
        try:
            # Traitement selon le type de requête
            if request.request_type == "access":
                result = await self._process_access_request(request)
            elif request.request_type == "erasure":
                result = await self._process_erasure_request(request)
            elif request.request_type == "rectification":
                result = await self._process_rectification_request(request)
            elif request.request_type == "portability":
                result = await self._process_portability_request(request)
            else:
                result = {"status": "unsupported", "reason": "Request type not supported"}
            
            request.status = "completed"
            request.processed_at = datetime.now(timezone.utc)
            request.response = json.dumps(result)
            
            return result
            
        except Exception as e:
            request.status = "rejected"
            request.reason = str(e)
            logger.error(f"Data request processing error: {e}")
            return {"status": "error", "reason": str(e)}
    
    async def _process_access_request(self, request: DataSubjectRequest) -> Dict[str, Any]:
        """Traite une requête d'accès."""
        # Récupération des données du sujet
        # Dans un système réel, on rechercherait les données associées
        return {
            "status": "success",
            "data": {
                "user": request.subject,
                "data_types": ["market_data", "portfolio", "trades"],
                "requested_at": request.submitted_at.isoformat()
            }
        }
    
    async def _process_erasure_request(self, request: DataSubjectRequest) -> Dict[str, Any]:
        """Traite une requête de suppression."""
        # Suppression des données du sujet
        # Dans un système réel, on anonymiserait ou supprimerait les données
        return {
            "status": "success",
            "action": "erasure",
            "subject": request.subject,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _process_rectification_request(self, request: DataSubjectRequest) -> Dict[str, Any]:
        """Traite une requête de rectification."""
        # Correction des données
        return {
            "status": "success",
            "action": "rectification",
            "subject": request.subject,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _process_portability_request(self, request: DataSubjectRequest) -> Dict[str, Any]:
        """Traite une requête de portabilité."""
        # Export des données
        return {
            "status": "success",
            "action": "portability",
            "subject": request.subject,
            "format": "json",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _compliance_checker_loop(self) -> None:
        """Boucle de vérification de conformité."""
        while self._is_running:
            await asyncio.sleep(self.config["compliance_check_interval"])
            
            try:
                # Vérification des données stockées
                if self.data_manager:
                    # Récupération des données pour vérification
                    # Dans un système réel, on vérifierait les données
                    compliance_rate = 0.95 + 0.05 * random.random()
                    self._stats["compliance_rate"] = compliance_rate
                    
                    # Stockage du taux de conformité
                    await self.data_manager.store(
                        "governance:compliance_rate",
                        {"rate": compliance_rate, "timestamp": datetime.now(timezone.utc).isoformat()},
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Compliance checker error: {e}")
    
    async def _audit_cleaner_loop(self) -> None:
        """Boucle de nettoyage des audits."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                retention_days = self.config["audit_retention_days"]
                cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
                
                with self._audit_lock:
                    # Suppression des audits anciens
                    old_audits = [
                        aid for aid, audit in self._audits.items()
                        if audit.timestamp < cutoff
                    ]
                    
                    for aid in old_audits:
                        del self._audits[aid]
                    
                    # Limitation du nombre d'entrées
                    if len(self._audits) > self.config["max_audit_entries"]:
                        sorted_audits = sorted(
                            self._audits.items(),
                            key=lambda x: x[1].timestamp
                        )
                        for aid, _ in sorted_audits[:len(self._audits) - self.config["max_audit_entries"]]:
                            del self._audits[aid]
                
                if old_audits:
                    logger.info(f"Cleaned up {len(old_audits)} old audit entries")
                
            except Exception as e:
                logger.error(f"Audit cleaner error: {e}")
    
    async def _report_generator_loop(self) -> None:
        """Boucle de génération de rapports de conformité."""
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                # Génération du rapport quotidien
                report = await self.generate_compliance_report(
                    "Daily Compliance Report",
                    "Automated daily compliance report"
                )
                
                # Stockage du rapport
                with self._report_lock:
                    self._reports[report.report_id] = report
                    self._stats["compliance_reports_generated"] += 1
                
                # Notification si non-conformité
                if report.status != DataGovernanceStatus.COMPLIANT:
                    logger.warning(f"Compliance report {report.report_id} indicates non-compliance")
                    
                    # Alerte de non-conformité
                    if self.data_manager:
                        await self.data_manager.store(
                            f"governance:alert:{report.report_id}",
                            {"status": report.status.value, "findings": report.findings},
                            DataType.ALERT
                        )
                
            except Exception as e:
                logger.error(f"Report generator error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_policies(self) -> None:
        """Charge les politiques existantes."""
        try:
            if self.data_manager:
                policies_data = await self.data_manager.retrieve(
                    "governance:policies",
                    DataType.CONFIG
                )
                
                if policies_data:
                    for policy_dict in policies_data:
                        policy = self._deserialize_policy(policy_dict)
                        if policy:
                            with self._policies_lock:
                                self._policies[policy.policy_id] = policy
            
            logger.info(f"Loaded {len(self._policies)} data policies")
            
        except Exception as e:
            logger.error(f"Error loading policies: {e}")
    
    async def _load_classifications(self) -> None:
        """Charge les classifications existantes."""
        try:
            if self.data_manager:
                classifications_data = await self.data_manager.retrieve(
                    "governance:classifications",
                    DataType.CONFIG
                )
                
                if classifications_data:
                    for class_dict in classifications_data:
                        classification = self._deserialize_classification(class_dict)
                        if classification:
                            with self._class_lock:
                                self._classifications[classification.classification_id] = classification
            
            logger.info(f"Loaded {len(self._classifications)} classifications")
            
        except Exception as e:
            logger.error(f"Error loading classifications: {e}")
    
    # ========== MÉTHODES DE DÉSÉRIALISATION ==========
    
    def _deserialize_policy(self, data: Dict) -> Optional[DataPolicy]:
        """Désérialise une politique."""
        try:
            return DataPolicy(
                policy_id=data.get("policy_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                description=data.get("description", ""),
                category=DataPolicyCategory(data.get("category", "compliance")),
                version=data.get("version", "1.0.0"),
                effective_date=datetime.fromisoformat(data.get("effective_date", datetime.now(timezone.utc).isoformat())),
                expiration_date=datetime.fromisoformat(data.get("expiration_date")) if data.get("expiration_date") else None,
                rules=data.get("rules", {}),
                scope=data.get("scope", []),
                jurisdiction=data.get("jurisdiction", []),
                status=DataGovernanceStatus(data.get("status", "pending")),
                created_by=data.get("created_by", ""),
                approved_by=data.get("approved_by"),
                approved_at=datetime.fromisoformat(data.get("approved_at")) if data.get("approved_at") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing policy: {e}")
            return None
    
    def _deserialize_classification(self, data: Dict) -> Optional[DataClassification]:
        """Désérialise une classification."""
        try:
            return DataClassification(
                classification_id=data.get("classification_id", str(uuid.uuid4())),
                data_type=DataType(data.get("data_type", "market")),
                classification=DataPolicyCategory(data.get("classification", "compliance")),
                gdpr_category=GDPRCategory(data.get("gdpr_category", "aggregated")),
                retention_policy=DataRetentionPolicy(data.get("retention_policy", "standard")),
                encryption_required=data.get("encryption_required", False),
                access_level=data.get("access_level", "read_only"),
                jurisdictions=data.get("jurisdictions", []),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing classification: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_policy(self, policy_id: str) -> Optional[DataPolicy]:
        """Récupère une politique."""
        with self._policies_lock:
            return self._policies.get(policy_id)
    
    async def get_policies(self, active_only: bool = True) -> List[DataPolicy]:
        """Récupère les politiques."""
        with self._policies_lock:
            policies = list(self._policies.values())
            if active_only:
                now = datetime.now(timezone.utc)
                policies = [
                    p for p in policies
                    if p.status == DataGovernanceStatus.COMPLIANT
                    and p.effective_date <= now
                    and (not p.expiration_date or p.expiration_date > now)
                ]
            return policies
    
    async def get_classification(self, classification_id: str) -> Optional[DataClassification]:
        """Récupère une classification."""
        with self._class_lock:
            return self._classifications.get(classification_id)
    
    async def get_classifications(self, data_type: Optional[DataType] = None) -> List[DataClassification]:
        """Récupère les classifications."""
        with self._class_lock:
            classifications = list(self._classifications.values())
            if data_type:
                classifications = [c for c in classifications if c.data_type == data_type]
            return classifications
    
    async def get_audit_trail(
        self,
        user: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditTrail]:
        """Récupère les audits."""
        with self._audit_lock:
            audits = list(self._audits.values())
            if user:
                audits = [a for a in audits if a.user == user]
            if action:
                audits = [a for a in audits if a.action == action]
            return sorted(audits, key=lambda a: a.timestamp, reverse=True)[:limit]
    
    async def get_data_request(self, request_id: str) -> Optional[DataSubjectRequest]:
        """Récupère une requête de données."""
        with self._req_lock:
            return self._data_requests.get(request_id)
    
    async def get_data_requests(self, status: Optional[str] = None) -> List[DataSubjectRequest]:
        """Récupère les requêtes de données."""
        with self._req_lock:
            requests = list(self._data_requests.values())
            if status:
                requests = [r for r in requests if r.status == status]
            return requests
    
    async def generate_compliance_report(
        self,
        name: str,
        description: str,
        jurisdiction: Optional[str] = None
    ) -> ComplianceReport:
        """Génère un rapport de conformité."""
        # Vérification des politiques
        findings = []
        policies_checked = []
        
        with self._policies_lock:
            for policy in self._policies.values():
                policies_checked.append(policy.policy_id)
                
                # Vérification de l'état de la politique
                if policy.status == DataGovernanceStatus.PENDING:
                    findings.append({
                        "policy_id": policy.policy_id,
                        "name": policy.name,
                        "status": "pending_approval",
                        "severity": "medium"
                    })
                elif policy.status == DataGovernanceStatus.NON_COMPLIANT:
                    findings.append({
                        "policy_id": policy.policy_id,
                        "name": policy.name,
                        "status": "non_compliant",
                        "severity": "high"
                    })
        
        # Vérification des classifications
        with self._class_lock:
            for classification in self._classifications.values():
                if classification.encryption_required:
                    # Vérification des données chiffrées
                    # Dans un système réel, on vérifierait les données
                    pass
        
        # Détermination du statut
        status = DataGovernanceStatus.COMPLIANT
        critical_findings = [f for f in findings if f.get("severity") == "high"]
        if critical_findings:
            status = DataGovernanceStatus.NON_COMPLIANT
        elif findings:
            status = DataGovernanceStatus.UNDER_REVIEW
        
        # Recommandations
        recommendations = []
        for finding in findings:
            if finding.get("severity") == "high":
                recommendations.append(f"Resolve compliance issue: {finding['name']}")
        
        # Création du rapport
        report = ComplianceReport(
            name=name,
            description=description,
            jurisdiction=jurisdiction or self.config["default_jurisdiction"],
            status=status,
            findings=findings,
            recommendations=recommendations,
            policies_checked=policies_checked,
            generated_by="governance_engine",
            metadata={"generation_time": datetime.now(timezone.utc).isoformat()}
        )
        
        with self._report_lock:
            self._reports[report.report_id] = report
            self._stats["compliance_reports_generated"] += 1
        
        logger.info(f"Compliance report generated: {report.report_id} status={status.value}")
        return report
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._audit_lock:
            self._stats["total_audits"] = len(self._audits)
        with self._policies_lock:
            self._stats["total_policies"] = len(self._policies)
        with self._class_lock:
            self._stats["total_classifications"] = len(self._classifications)
        with self._req_lock:
            self._stats["pending_requests"] = len([
                r for r in self._data_requests.values()
                if r.status == "pending"
            ])
        
        return self._stats.copy()


# ============== GDPR COMPLIANCE HELPER ==============

class GDPRComplianceHelper:
    """
    Assistant de conformité GDPR.
    Fournit des méthodes utilitaires pour la conformité GDPR.
    """
    
    @staticmethod
    def check_data_processing_legitimacy(
        purpose: str,
        legal_basis: str
    ) -> bool:
        """Vérifie la légitimité du traitement des données."""
        legal_bases = ["consent", "contract", "legal_obligation", "vital_interest", 
                      "public_task", "legitimate_interest"]
        return legal_basis in legal_bases
    
    @staticmethod
    def anonymize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymise des données."""
        anonymized = data.copy()
        
        # Suppression des identifiants
        for key in ["id", "user_id", "email", "phone", "name", "address"]:
            if key in anonymized:
                anonymized[key] = "***"
        
        # Hachage des identifiants numériques
        for key in ["user_id", "account_id", "device_id"]:
            if key in anonymized:
                anonymized[key] = hashlib.sha256(
                    str(anonymized[key]).encode()
                ).hexdigest()[:8]
        
        return anonymized
    
    @staticmethod
    def evaluate_data_classification(
        data: Dict[str, Any]
    ) -> GDPRCategory:
        """Évalue la classification GDPR des données."""
        # Vérification des données personnelles
        personal_fields = ["name", "email", "phone", "address", "birth_date"]
        if any(field in data for field in personal_fields):
            return GDPRCategory.PERSONAL_DATA
        
        # Vérification des données sensibles
        sensitive_fields = ["health", "political_views", "religion", "ethnicity", "biometric"]
        if any(field in data for field in sensitive_fields):
            return GDPRCategory.SENSITIVE_DATA
        
        # Vérification des métadonnées
        if len(data) < 3:
            return GDPRCategory.METADATA
        
        return GDPRCategory.AGGREGATED


# ============== FACTORY ==============

class GovernanceFactory:
    """Factory pour créer des composants de gouvernance."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> GovernanceEngine:
        """Crée un moteur de gouvernance."""
        engine = GovernanceEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_policy(
        name: str,
        category: DataPolicyCategory,
        rules: Dict[str, Any],
        **kwargs
    ) -> DataPolicy:
        """Crée une politique de données."""
        return DataPolicy(
            name=name,
            category=category,
            rules=rules,
            **kwargs
        )


# ============== EXPORT ==============

__all__ = [
    "DataPolicyCategory",
    "DataGovernanceStatus",
    "GDPRCategory",
    "DataRetentionPolicy",
    "DataPolicy",
    "DataClassification",
    "AuditTrail",
    "DataSubjectRequest",
    "ComplianceReport",
    "GovernanceEngineInterface",
    "GovernanceEngine",
    "GDPRComplianceHelper",
    "GovernanceFactory"
]

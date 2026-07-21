"""
NEXUS AI TRADING SYSTEM - HEDGE BOT AUDIT MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion d'audit pour le Hedge Bot.
Traçabilité, logging, conformité, et reporting d'audit.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import json
import logging
import os
import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiofiles
import psutil
from cryptography.fernet import Fernet
from elasticsearch import AsyncElasticsearch

from ..utils.helpers import now_utc, safe_json, is_valid_uuid

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class AuditSeverity(Enum):
    """Niveaux de sévérité d'audit."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


class AuditCategory(Enum):
    """Catégories d'audit."""
    SYSTEM = "system"
    USER = "user"
    TRADING = "trading"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    CONFIGURATION = "configuration"
    DATA = "data"
    NETWORK = "network"
    APPLICATION = "application"


class AuditAction(Enum):
    """Actions d'audit."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    APPROVE = "approve"
    REJECT = "reject"
    SUSPEND = "suspend"
    ACTIVATE = "activate"
    MODIFY = "modify"
    TRANSFER = "transfer"
    TRADE = "trade"
    CONFIG = "config"
    BACKUP = "backup"
    RESTORE = "restore"
    EXPORT = "export"
    IMPORT = "import"


@dataclass
class AuditLog:
    """Enregistrement d'audit."""
    log_id: UUID
    timestamp: datetime
    category: AuditCategory
    action: AuditAction
    severity: AuditSeverity
    user_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[UUID] = None
    source: Optional[str] = None
    hostname: Optional[str] = None
    process_id: Optional[int] = None
    thread_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "log_id": str(self.log_id),
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "action": self.action.value,
            "severity": self.severity.value,
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": str(self.session_id) if self.session_id else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "message": self.message,
            "metadata": self.metadata,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "source": self.source,
            "hostname": self.hostname,
            "process_id": self.process_id,
            "thread_id": self.thread_id
        }


@dataclass
class AuditReport:
    """Rapport d'audit."""
    report_id: UUID
    user_id: UUID
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    total_entries: int
    by_category: Dict[str, int]
    by_action: Dict[str, int]
    by_severity: Dict[str, int]
    entries: List[AuditLog]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_entries": self.total_entries,
            "by_category": self.by_category,
            "by_action": self.by_action,
            "by_severity": self.by_severity,
            "entries": [e.to_dict() for e in self.entries],
            "summary": self.summary,
            "metadata": self.metadata
        }


@dataclass
class ComplianceRule:
    """Règle de conformité."""
    rule_id: UUID
    name: str
    description: str
    category: AuditCategory
    condition: str
    severity: AuditSeverity
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "rule_id": str(self.rule_id),
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "condition": self.condition,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE AUDIT MANAGER
# ============================================================================

class AuditManager:
    """
    Gestionnaire d'audit avancé.
    """

    # Périodes de rétention par défaut
    DEFAULT_RETENTION_DAYS = 90
    CRITICAL_RETENTION_DAYS = 365

    def __init__(
        self,
        elasticsearch_url: Optional[str] = None,
        redis_client: Optional[Any] = None,
        encryption_key: Optional[str] = None,
        log_file_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire d'audit.

        Args:
            elasticsearch_url: URL de connexion Elasticsearch
            redis_client: Client Redis pour le cache
            encryption_key: Clé de chiffrement
            log_file_path: Chemin du fichier de logs
            config: Configuration
        """
        self.elasticsearch_url = elasticsearch_url
        self.redis = redis_client
        self.encryption_key = encryption_key
        self.log_file_path = log_file_path or "logs/audit.log"
        self.config = config or {}
        
        # Elasticsearch client
        self._es_client = None
        
        # Fernet pour chiffrement
        self._fernet = None
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())
        
        # Cache
        self._audit_cache: Dict[UUID, AuditLog] = {}
        self._compliance_cache: Dict[UUID, ComplianceRule] = {}
        
        # Métriques
        self._metrics = {
            "total_logs": 0,
            "by_category": {},
            "by_action": {},
            "by_severity": {},
            "last_log": None,
            "compliance_violations": 0
        }

        # Initialisation
        if elasticsearch_url:
            self._init_elasticsearch()

        logger.info("AuditManager initialisé avec succès")

    def _init_elasticsearch(self) -> None:
        """Initialise le client Elasticsearch."""
        try:
            self._es_client = AsyncElasticsearch([self.elasticsearch_url])
            logger.info("Elasticsearch client initialisé")
        except Exception as e:
            logger.error(f"Erreur d'initialisation Elasticsearch: {e}")

    # ========================================================================
    # ENREGISTREMENT D'AUDIT
    # ========================================================================

    async def log(
        self,
        category: AuditCategory,
        action: AuditAction,
        severity: AuditSeverity,
        user_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict] = None,
        correlation_id: Optional[UUID] = None
    ) -> AuditLog:
        """
        Enregistre un événement d'audit.

        Args:
            category: Catégorie
            action: Action
            severity: Sévérité
            user_id: ID de l'utilisateur
            session_id: ID de la session
            ip_address: Adresse IP
            user_agent: User agent
            resource_type: Type de ressource
            resource_id: ID de la ressource
            old_value: Ancienne valeur
            new_value: Nouvelle valeur
            message: Message
            metadata: Métadonnées
            correlation_id: ID de corrélation

        Returns:
            Enregistrement d'audit
        """
        try:
            log_id = uuid4()
            now = datetime.now()

            # Informations système
            hostname = socket.gethostname()
            process_id = os.getpid()
            thread_id = threading.get_ident() if 'threading' in dir() else None

            # Chiffrement des données sensibles
            if self._fernet:
                if old_value and isinstance(old_value, (dict, list)):
                    old_value = self._encrypt_data(old_value)
                if new_value and isinstance(new_value, (dict, list)):
                    new_value = self._encrypt_data(new_value)

            audit_log = AuditLog(
                log_id=log_id,
                timestamp=now,
                category=category,
                action=action,
                severity=severity,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type=resource_type,
                resource_id=resource_id,
                old_value=old_value,
                new_value=new_value,
                message=message,
                metadata=metadata or {},
                correlation_id=correlation_id or uuid4(),
                source=self.config.get("source", "hedge_bot"),
                hostname=hostname,
                process_id=process_id,
                thread_id=thread_id
            )

            # Stockage en cache
            self._audit_cache[log_id] = audit_log

            # Mise à jour des métriques
            self._metrics["total_logs"] += 1
            self._metrics["last_log"] = now.isoformat()

            category_key = category.value
            if category_key not in self._metrics["by_category"]:
                self._metrics["by_category"][category_key] = 0
            self._metrics["by_category"][category_key] += 1

            action_key = action.value
            if action_key not in self._metrics["by_action"]:
                self._metrics["by_action"][action_key] = 0
            self._metrics["by_action"][action_key] += 1

            severity_key = severity.value
            if severity_key not in self._metrics["by_severity"]:
                self._metrics["by_severity"][severity_key] = 0
            self._metrics["by_severity"][severity_key] += 1

            # Sauvegarde dans Elasticsearch
            if self._es_client:
                await self._index_in_elasticsearch(audit_log)

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_audit_log(audit_log)

            # Écriture dans le fichier de logs
            await self._write_to_file(audit_log)

            # Vérification de conformité
            await self._check_compliance(audit_log)

            return audit_log

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement d'audit: {e}")
            raise

    def _encrypt_data(self, data: Any) -> str:
        """
        Chiffre des données.

        Args:
            data: Données à chiffrer

        Returns:
            Données chiffrées
        """
        try:
            json_data = json.dumps(data)
            encrypted = self._fernet.encrypt(json_data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Erreur de chiffrement: {e}")
            return str(data)

    def _decrypt_data(self, encrypted: str) -> Any:
        """
        Déchiffre des données.

        Args:
            encrypted: Données chiffrées

        Returns:
            Données déchiffrées
        """
        try:
            decrypted = self._fernet.decrypt(encrypted.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Erreur de déchiffrement: {e}")
            return encrypted

    # ========================================================================
    # RÉCUPÉRATION DES LOGS
    # ========================================================================

    async def get_logs(
        self,
        user_id: Optional[UUID] = None,
        category: Optional[AuditCategory] = None,
        action: Optional[AuditAction] = None,
        severity: Optional[AuditSeverity] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Récupère les logs d'audit.

        Args:
            user_id: Filtrer par utilisateur
            category: Filtrer par catégorie
            action: Filtrer par action
            severity: Filtrer par sévérité
            from_date: Date de début
            to_date: Date de fin
            search: Recherche textuelle
            limit: Nombre de logs
            offset: Décalage

        Returns:
            Liste des logs d'audit
        """
        try:
            logs = list(self._audit_cache.values())

            if user_id:
                logs = [l for l in logs if l.user_id == user_id]
            if category:
                logs = [l for l in logs if l.category == category]
            if action:
                logs = [l for l in logs if l.action == action]
            if severity:
                logs = [l for l in logs if l.severity == severity]
            if from_date:
                logs = [l for l in logs if l.timestamp >= from_date]
            if to_date:
                logs = [l for l in logs if l.timestamp <= to_date]
            if search:
                logs = [l for l in logs if search.lower() in str(l.to_dict()).lower()]

            logs.sort(key=lambda x: x.timestamp, reverse=True)
            return logs[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des logs: {e}")
            return []

    async def get_log_by_id(
        self,
        log_id: UUID
    ) -> Optional[AuditLog]:
        """
        Récupère un log par son ID.

        Args:
            log_id: ID du log

        Returns:
            Log ou None
        """
        return self._audit_cache.get(log_id)

    # ========================================================================
    # RAPPORTS D'AUDIT
    # ========================================================================

    async def generate_report(
        self,
        user_id: UUID,
        period_days: int = 30,
        category: Optional[AuditCategory] = None,
        action: Optional[AuditAction] = None,
        severity: Optional[AuditSeverity] = None
    ) -> AuditReport:
        """
        Génère un rapport d'audit.

        Args:
            user_id: ID de l'utilisateur
            period_days: Période en jours
            category: Filtrer par catégorie
            action: Filtrer par action
            severity: Filtrer par sévérité

        Returns:
            Rapport d'audit
        """
        try:
            now = datetime.now()
            period_start = now - timedelta(days=period_days)

            logs = await self.get_logs(
                user_id=user_id,
                category=category,
                action=action,
                severity=severity,
                from_date=period_start,
                to_date=now
            )

            by_category = {}
            by_action = {}
            by_severity = {}

            for log in logs:
                cat_key = log.category.value
                if cat_key not in by_category:
                    by_category[cat_key] = 0
                by_category[cat_key] += 1

                act_key = log.action.value
                if act_key not in by_action:
                    by_action[act_key] = 0
                by_action[act_key] += 1

                sev_key = log.severity.value
                if sev_key not in by_severity:
                    by_severity[sev_key] = 0
                by_severity[sev_key] += 1

            summary = {
                "period_days": period_days,
                "category": category.value if category else "all",
                "action": action.value if action else "all",
                "severity": severity.value if severity else "all"
            }

            report = AuditReport(
                report_id=uuid4(),
                user_id=user_id,
                generated_at=datetime.now(),
                period_start=period_start,
                period_end=now,
                total_entries=len(logs),
                by_category=by_category,
                by_action=by_action,
                by_severity=by_severity,
                entries=logs[:1000],  # Limite pour la performance
                summary=summary
            )

            return report

        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport: {e}")
            raise

    # ========================================================================
    # CONFORMITÉ
    # ========================================================================

    async def add_compliance_rule(
        self,
        name: str,
        description: str,
        category: AuditCategory,
        condition: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        metadata: Optional[Dict] = None
    ) -> ComplianceRule:
        """
        Ajoute une règle de conformité.

        Args:
            name: Nom de la règle
            description: Description
            category: Catégorie
            condition: Condition
            severity: Sévérité
            metadata: Métadonnées

        Returns:
            Règle de conformité
        """
        try:
            rule = ComplianceRule(
                rule_id=uuid4(),
                name=name,
                description=description,
                category=category,
                condition=condition,
                severity=severity,
                metadata=metadata or {}
            )

            self._compliance_cache[rule.rule_id] = rule
            return rule

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la règle: {e}")
            raise

    async def _check_compliance(
        self,
        audit_log: AuditLog
    ) -> None:
        """
        Vérifie la conformité d'un log.

        Args:
            audit_log: Log à vérifier
        """
        for rule in self._compliance_cache.values():
            if not rule.enabled:
                continue

            if rule.category != audit_log.category:
                continue

            try:
                # Évaluation de la condition
                # Pour l'exemple, nous utilisons une évaluation simple
                # En production, utiliser un moteur de règles
                if self._evaluate_condition(rule.condition, audit_log):
                    self._metrics["compliance_violations"] += 1
                    
                    # Log de la violation
                    await self.log(
                        category=AuditCategory.COMPLIANCE,
                        action=AuditAction.APPROVE,
                        severity=rule.severity,
                        message=f"Violation de conformité: {rule.name}",
                        metadata={
                            "rule_id": str(rule.rule_id),
                            "violating_log": audit_log.log_id
                        }
                    )
            except Exception as e:
                logger.error(f"Erreur d'évaluation de la règle {rule.name}: {e}")

    def _evaluate_condition(
        self,
        condition: str,
        audit_log: AuditLog
    ) -> bool:
        """
        Évalue une condition de conformité.

        Args:
            condition: Condition à évaluer
            audit_log: Log à vérifier

        Returns:
            True si la condition est satisfaite
        """
        # Implémentation simplifiée
        # En production, utiliser un moteur de règles comme PyKE ou Rule Engine
        try:
            # Exemple: "action == 'DELETE' and severity == 'CRITICAL'"
            # Pour l'exemple, nous utilisons une évaluation simple
            if "action" in condition:
                action = condition.split("'")[1] if "'" in condition else condition.split('"')[1]
                return audit_log.action.value == action
            return False
        except Exception:
            return False

    # ========================================================================
    # STOCKAGE
    # ========================================================================

    async def _index_in_elasticsearch(self, audit_log: AuditLog) -> None:
        """
        Indexe un log dans Elasticsearch.

        Args:
            audit_log: Log à indexer
        """
        try:
            if self._es_client:
                index = f"audit-{audit_log.timestamp.strftime('%Y.%m')}"
                await self._es_client.index(
                    index=index,
                    id=str(audit_log.log_id),
                    document=audit_log.to_dict()
                )
        except Exception as e:
            logger.error(f"Erreur d'indexation Elasticsearch: {e}")

    async def _save_audit_log(self, audit_log: AuditLog) -> None:
        """
        Sauvegarde un log dans Redis.

        Args:
            audit_log: Log à sauvegarder
        """
        try:
            key = f"audit:{audit_log.log_id}"
            await self.redis.setex(
                key,
                86400 * self.DEFAULT_RETENTION_DAYS,
                json.dumps(audit_log.to_dict())
            )
        except Exception as e:
            logger.error(f"Erreur de sauvegarde Redis: {e}")

    async def _write_to_file(self, audit_log: AuditLog) -> None:
        """
        Écrit un log dans un fichier.

        Args:
            audit_log: Log à écrire
        """
        try:
            log_line = json.dumps(audit_log.to_dict()) + "\n"
            
            # Création du répertoire si nécessaire
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            
            async with aiofiles.open(self.log_file_path, 'a') as f:
                await f.write(log_line)
        except Exception as e:
            logger.error(f"Erreur d'écriture du fichier: {e}")

    # ========================================================================
    # EXPORT
    # ========================================================================

    async def export_logs(
        self,
        user_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        format: str = "json"
    ) -> Union[str, bytes]:
        """
        Exporte les logs d'audit.

        Args:
            user_id: ID de l'utilisateur
            from_date: Date de début
            to_date: Date de fin
            format: Format d'export (json, csv)

        Returns:
            Données exportées
        """
        try:
            logs = await self.get_logs(
                user_id=user_id,
                from_date=from_date,
                to_date=to_date
            )

            if format == "csv":
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=logs[0].to_dict().keys() if logs else [])
                writer.writeheader()
                for log in logs:
                    writer.writerow(log.to_dict())
                return output.getvalue()

            else:  # json
                return json.dumps([l.to_dict() for l in logs], indent=2)

        except Exception as e:
            logger.error(f"Erreur d'export: {e}")
            return ""

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
                "total_logs": self._metrics["total_logs"],
                "by_category": self._metrics["by_category"],
                "by_action": self._metrics["by_action"],
                "by_severity": self._metrics["by_severity"],
                "last_log": self._metrics["last_log"],
                "compliance_violations": self._metrics["compliance_violations"],
                "cached_logs": len(self._audit_cache),
                "compliance_rules": len(self._compliance_cache),
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
        logger.info("Fermeture de AuditManager...")
        
        if self._es_client:
            await self._es_client.close()
        
        self._audit_cache.clear()
        self._compliance_cache.clear()
        logger.info("AuditManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_audit_manager(
    elasticsearch_url: Optional[str] = None,
    redis_url: str = "redis://localhost:6379/0",
    encryption_key: Optional[str] = None,
    log_file_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> AuditManager:
    """
    Crée une instance de AuditManager.

    Args:
        elasticsearch_url: URL de connexion Elasticsearch
        redis_url: URL de connexion Redis
        encryption_key: Clé de chiffrement
        log_file_path: Chemin du fichier de logs
        config: Configuration

    Returns:
        Instance de AuditManager
    """
    import redis.asyncio as redis
    import threading
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return AuditManager(
        elasticsearch_url=elasticsearch_url,
        redis_client=redis_client,
        encryption_key=encryption_key,
        log_file_path=log_file_path,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AuditSeverity",
    "AuditCategory",
    "AuditAction",
    "AuditLog",
    "AuditReport",
    "ComplianceRule",
    "AuditManager",
    "create_audit_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire d'audit."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT AUDIT MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    audit_manager = create_audit_manager()

    print(f"\n✅ AuditManager initialisé")

    # Enregistrement d'un log
    print(f"\n📝 Enregistrement d'un log...")
    log = await audit_manager.log(
        category=AuditCategory.USER,
        action=AuditAction.LOGIN,
        severity=AuditSeverity.INFO,
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        ip_address="192.168.1.1",
        message="Connexion utilisateur réussie",
        metadata={"method": "api_key"}
    )

    print(f"   ID: {log.log_id}")
    print(f"   Catégorie: {log.category.value}")
    print(f"   Action: {log.action.value}")
    print(f"   Message: {log.message}")

    # Enregistrement d'une action critique
    print(f"\n⚠️ Enregistrement d'une action critique...")
    critical_log = await audit_manager.log(
        category=AuditCategory.SECURITY,
        action=AuditAction.DELETE,
        severity=AuditSeverity.CRITICAL,
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        resource_type="wallet",
        resource_id="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        message="Suppression de wallet demandée",
        metadata={"reason": "security_breach"}
    )

    print(f"   Log critique: {critical_log.log_id}")

    # Ajout d'une règle de conformité
    print(f"\n📋 Ajout d'une règle de conformité...")
    rule = await audit_manager.add_compliance_rule(
        name="Suppression Critique",
        description="Toute suppression de ressource critique",
        category=AuditCategory.SECURITY,
        condition="action == 'DELETE'",
        severity=AuditSeverity.CRITICAL
    )

    print(f"   Règle: {rule.name}")

    # Récupération des logs
    print(f"\n📖 Récupération des logs...")
    logs = await audit_manager.get_logs(limit=5)
    print(f"   {len(logs)} logs récupérés")

    # Génération d'un rapport
    print(f"\n📊 Génération d'un rapport...")
    report = await audit_manager.generate_report(
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        period_days=1
    )

    print(f"   Rapport: {report.report_id}")
    print(f"   Entrées: {report.total_entries}")
    print(f"   Par catégorie: {report.by_category}")

    # Santé du service
    health = await audit_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Logs: {health['total_logs']}")
    print(f"   Violations de conformité: {health['compliance_violations']}")

    # Fermeture
    await audit_manager.close()

    print("\n" + "=" * 60)
    print("AuditManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import threading
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

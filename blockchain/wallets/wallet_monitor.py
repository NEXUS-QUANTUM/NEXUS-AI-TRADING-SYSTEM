"""
NEXUS AI TRADING SYSTEM - WALLET MONITOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de surveillance avancée des wallets multi-blockchain.
Suivi en temps réel des transactions, alertes, analytics, et reporting.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import numpy as np
from web3 import Web3

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class MonitorEventType(Enum):
    """Types d'événements de monitoring."""
    TRANSACTION = "transaction"
    BALANCE_CHANGE = "balance_change"
    PRICE_CHANGE = "price_change"
    GAS_PRICE = "gas_price"
    NETWORK_STATUS = "network_status"
    ANOMALY = "anomaly"
    THRESHOLD = "threshold"
    HEALTH = "health"
    SECURITY = "security"
    PERFORMANCE = "performance"


class MonitorSeverity(Enum):
    """Niveaux de sévérité des événements."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MonitorEvent:
    """Événement de monitoring."""
    event_id: UUID
    wallet_id: UUID
    event_type: MonitorEventType
    severity: MonitorSeverity
    title: str
    description: str
    data: Dict[str, Any]
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "event_id": str(self.event_id),
            "wallet_id": str(self.wallet_id),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata
        }


@dataclass
class MonitorAlert:
    """Alerte de monitoring."""
    alert_id: UUID
    wallet_id: UUID
    user_id: UUID
    condition: str
    threshold: Any
    current_value: Any
    severity: MonitorSeverity
    message: str
    triggered_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "alert_id": str(self.alert_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "condition": self.condition,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "severity": self.severity.value,
            "message": self.message,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "metadata": self.metadata
        }


@dataclass
class MonitorMetrics:
    """Métriques de monitoring."""
    wallet_id: UUID
    total_transactions: int
    total_volume_usd: Decimal
    average_tx_value_usd: Decimal
    max_tx_value_usd: Decimal
    tx_count_last_24h: int
    tx_count_last_7d: int
    active_addresses: int
    unique_contracts: int
    success_rate: float
    error_rate: float
    average_confirmation_time: float
    uptime_percentage: float
    last_block: int
    last_sync: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "total_transactions": self.total_transactions,
            "total_volume_usd": str(self.total_volume_usd),
            "average_tx_value_usd": str(self.average_tx_value_usd),
            "max_tx_value_usd": str(self.max_tx_value_usd),
            "tx_count_last_24h": self.tx_count_last_24h,
            "tx_count_last_7d": self.tx_count_last_7d,
            "active_addresses": self.active_addresses,
            "unique_contracts": self.unique_contracts,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "average_confirmation_time": self.average_confirmation_time,
            "uptime_percentage": self.uptime_percentage,
            "last_block": self.last_block,
            "last_sync": self.last_sync.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET MONITOR
# ============================================================================

class WalletMonitor:
    """
    Service de surveillance avancée des wallets multi-blockchain.
    """

    # Seuils par défaut pour les alertes
    DEFAULT_THRESHOLDS = {
        "balance_change": {
            "warning": 0.10,  # 10% de changement
            "critical": 0.25,  # 25% de changement
            "emergency": 0.50  # 50% de changement
        },
        "gas_price": {
            "warning": 50,  # 50 GWEI
            "critical": 100,  # 100 GWEI
            "emergency": 200  # 200 GWEI
        },
        "transaction_count": {
            "warning": 100,  # 100 transactions en 24h
            "critical": 500,  # 500 transactions en 24h
            "emergency": 1000  # 1000 transactions en 24h
        },
        "success_rate": {
            "warning": 0.90,  # 90% de succès
            "critical": 0.80,  # 80% de succès
            "emergency": 0.70  # 70% de succès
        },
        "balance": {
            "warning": 100,  # 100 USD
            "critical": 10,  # 10 USD
            "emergency": 1  # 1 USD
        }
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        webhook_urls: Optional[Dict[str, str]] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de monitoring.

        Args:
            redis_client: Client Redis pour le cache
            webhook_urls: URLs des webhooks pour les notifications
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.webhook_urls = webhook_urls or {}
        self.api_keys = api_keys or {}
        
        # Cache
        self._event_cache: Dict[UUID, List[MonitorEvent]] = {}
        self._alert_cache: Dict[UUID, List[MonitorAlert]] = {}
        self._metrics_cache: Dict[UUID, MonitorMetrics] = {}
        self._alert_configs: Dict[UUID, List[Dict]] = {}
        
        # État des wallets
        self._wallet_state: Dict[UUID, Dict] = {}
        self._last_block_cache: Dict[str, int] = {}
        
        # Métriques
        self._metrics = {
            "total_events": 0,
            "total_alerts": 0,
            "total_notifications": 0,
            "events_by_type": {},
            "alerts_by_severity": {},
            "last_event": None,
            "last_alert": None
        }

        logger.info("WalletMonitor initialisé avec succès")

    # ========================================================================
    # CONFIGURATION DES ALERTES
    # ========================================================================

    async def set_alert_config(
        self,
        wallet_id: UUID,
        config: Dict[str, Any]
    ) -> bool:
        """
        Configure les alertes pour un wallet.

        Args:
            wallet_id: ID du wallet
            config: Configuration des alertes

        Returns:
            True si la configuration a réussi
        """
        try:
            # Validation de la configuration
            required_fields = ["condition", "threshold", "severity", "message"]
            if not all(field in config for field in required_fields):
                logger.error("Configuration d'alerte invalide")
                return False

            alert_id = str(uuid4())
            config["alert_id"] = alert_id
            config["created_at"] = datetime.now().isoformat()

            if wallet_id not in self._alert_configs:
                self._alert_configs[wallet_id] = []
            
            self._alert_configs[wallet_id].append(config)

            # Sauvegarde dans Redis
            if self.redis:
                key = f"monitor:alert_config:{wallet_id}"
                await self.redis.setex(
                    key,
                    86400 * 30,
                    json.dumps(self._alert_configs[wallet_id])
                )

            logger.info(f"Configuration d'alerte ajoutée pour {wallet_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la configuration de l'alerte: {e}")
            return False

    async def get_alert_configs(
        self,
        wallet_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Récupère les configurations d'alertes.

        Args:
            wallet_id: ID du wallet

        Returns:
            Liste des configurations
        """
        try:
            if wallet_id in self._alert_configs:
                return self._alert_configs[wallet_id]

            # Récupération depuis Redis
            if self.redis:
                key = f"monitor:alert_config:{wallet_id}"
                data = await self.redis.get(key)
                if data:
                    configs = json.loads(data)
                    self._alert_configs[wallet_id] = configs
                    return configs

            return []

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des configurations: {e}")
            return []

    # ========================================================================
    # SURVEILLANCE DES TRANSACTIONS
    # ========================================================================

    async def monitor_transaction(
        self,
        wallet: BaseWallet,
        tx: Transaction
    ) -> Optional[MonitorEvent]:
        """
        Surveille une transaction et génère des événements.

        Args:
            wallet: Wallet
            tx: Transaction à surveiller

        Returns:
            Événement de monitoring ou None
        """
        try:
            wallet_id = wallet.config.wallet_id
            
            # Vérification du statut
            if tx.status == TransactionStatus.FAILED:
                event = await self._create_event(
                    wallet_id=wallet_id,
                    event_type=MonitorEventType.TRANSACTION,
                    severity=MonitorSeverity.ERROR,
                    title="Transaction échouée",
                    description=f"La transaction {tx.tx_hash[:8]}... a échoué",
                    data={
                        "tx_hash": tx.tx_hash,
                        "amount": str(tx.amount),
                        "amount_usd": str(tx.amount_usd),
                        "error": tx.error_message
                    }
                )
                await self._trigger_alert(
                    wallet_id=wallet_id,
                    alert_type="failed_transaction",
                    value=tx.amount,
                    metadata={"tx_hash": tx.tx_hash}
                )
                return event

            # Vérification du montant
            if tx.amount_usd > Decimal("1000"):
                event = await self._create_event(
                    wallet_id=wallet_id,
                    event_type=MonitorEventType.TRANSACTION,
                    severity=MonitorSeverity.WARNING,
                    title="Transaction de montant élevé",
                    description=f"Transaction de {tx.amount_usd:.2f} USD détectée",
                    data={
                        "tx_hash": tx.tx_hash,
                        "amount": str(tx.amount),
                        "amount_usd": str(tx.amount_usd)
                    }
                )
                return event

            # Vérification du type
            if tx.tx_type == TransactionType.SWAP:
                event = await self._create_event(
                    wallet_id=wallet_id,
                    event_type=MonitorEventType.TRANSACTION,
                    severity=MonitorSeverity.INFO,
                    title="Swap détecté",
                    description=f"Swap de {tx.amount:.4f} {tx.token_symbol or 'ETH'}",
                    data={
                        "tx_hash": tx.tx_hash,
                        "from": tx.from_address,
                        "to": tx.to_address,
                        "amount": str(tx.amount)
                    }
                )
                return event

            if tx.tx_type == TransactionType.STAKING:
                event = await self._create_event(
                    wallet_id=wallet_id,
                    event_type=MonitorEventType.TRANSACTION,
                    severity=MonitorSeverity.INFO,
                    title="Staking détecté",
                    description=f"Staking de {tx.amount:.4f} {tx.token_symbol or 'ETH'}",
                    data={
                        "tx_hash": tx.tx_hash,
                        "amount": str(tx.amount)
                    }
                )
                return event

            return None

        except Exception as e:
            logger.error(f"Erreur lors du monitoring de la transaction: {e}")
            return None

    async def monitor_wallet_activity(
        self,
        wallet: BaseWallet
    ) -> List[MonitorEvent]:
        """
        Surveille l'activité d'un wallet.

        Args:
            wallet: Wallet

        Returns:
            Liste des événements générés
        """
        events = []
        
        try:
            wallet_id = wallet.config.wallet_id
            
            # Récupération des transactions récentes
            transactions = await wallet.get_transactions(limit=100)
            
            # Analyse des transactions
            for tx in transactions:
                event = await self.monitor_transaction(wallet, tx)
                if event:
                    events.append(event)

            # Vérification du solde
            balance = await wallet.get_balance()
            balance_event = await self._check_balance_thresholds(
                wallet_id,
                balance.total_balance_usd
            )
            if balance_event:
                events.append(balance_event)

            # Vérification de l'activité
            activity_event = await self._check_activity(
                wallet_id,
                transactions
            )
            if activity_event:
                events.append(activity_event)

            # Mise à jour des métriques
            await self._update_metrics(wallet_id, transactions, balance)

            return events

        except Exception as e:
            logger.error(f"Erreur lors du monitoring de l'activité: {e}")
            return events

    # ========================================================================
    # SURVEILLANCE DES PRIX
    # ========================================================================

    async def monitor_prices(
        self,
        symbols: List[str],
        threshold: float = 5.0
    ) -> List[MonitorEvent]:
        """
        Surveille les prix des tokens.

        Args:
            symbols: Liste des symboles
            threshold: Seuil de changement en pourcentage

        Returns:
            Liste des événements générés
        """
        events = []

        try:
            for symbol in symbols:
                # Récupération du prix actuel
                current_price = await self._get_price(symbol)
                
                # Récupération du prix précédent
                previous_price = await self._get_previous_price(symbol)
                
                if previous_price and current_price:
                    change = abs((current_price - previous_price) / previous_price * 100)
                    
                    if change > threshold:
                        event = await self._create_event(
                            wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                            event_type=MonitorEventType.PRICE_CHANGE,
                            severity=MonitorSeverity.WARNING if change > threshold * 2 else MonitorSeverity.INFO,
                            title=f"Changement de prix {symbol}",
                            description=f"{symbol} a changé de {change:.2f}%",
                            data={
                                "symbol": symbol,
                                "current_price": current_price,
                                "previous_price": previous_price,
                                "change_percent": change
                            }
                        )
                        events.append(event)

                # Mise à jour du prix précédent
                if current_price:
                    await self._save_previous_price(symbol, current_price)

            return events

        except Exception as e:
            logger.error(f"Erreur lors du monitoring des prix: {e}")
            return events

    async def _get_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix d'un token.

        Args:
            symbol: Symbole du token

        Returns:
            Prix du token
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": symbol.lower(),
                        "vs_currencies": "usd"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get(symbol.lower(), {}).get("usd")
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix: {e}")
            return None

    async def _get_previous_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix précédent d'un token.

        Args:
            symbol: Symbole du token

        Returns:
            Prix précédent
        """
        try:
            if self.redis:
                key = f"monitor:price:{symbol}"
                data = await self.redis.get(key)
                if data:
                    return float(data)
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix précédent: {e}")
            return None

    async def _save_previous_price(
        self,
        symbol: str,
        price: float
    ) -> None:
        """
        Sauvegarde le prix précédent d'un token.

        Args:
            symbol: Symbole du token
            price: Prix à sauvegarder
        """
        try:
            if self.redis:
                key = f"monitor:price:{symbol}"
                await self.redis.setex(key, 3600, str(price))

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du prix: {e}")

    # ========================================================================
    # SURVEILLANCE DU RÉSEAU
    # ========================================================================

    async def monitor_network(
        self,
        blockchain: str
    ) -> Optional[MonitorEvent]:
        """
        Surveille l'état du réseau.

        Args:
            blockchain: Blockchain

        Returns:
            Événement de monitoring ou None
        """
        try:
            # Récupération du statut du réseau
            gas_price = await self._get_network_gas_price(blockchain)
            block_number = await self._get_network_block(blockchain)
            
            # Vérification des seuils de gaz
            thresholds = self.DEFAULT_THRESHOLDS["gas_price"]
            
            if gas_price > thresholds["emergency"]:
                return await self._create_event(
                    wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                    event_type=MonitorEventType.GAS_PRICE,
                    severity=MonitorSeverity.EMERGENCY,
                    title="Prix du gaz anormalement élevé",
                    description=f"Prix du gaz à {gas_price} GWEI",
                    data={
                        "blockchain": blockchain,
                        "gas_price": gas_price,
                        "block_number": block_number
                    }
                )
            elif gas_price > thresholds["critical"]:
                return await self._create_event(
                    wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                    event_type=MonitorEventType.GAS_PRICE,
                    severity=MonitorSeverity.CRITICAL,
                    title="Prix du gaz très élevé",
                    description=f"Prix du gaz à {gas_price} GWEI",
                    data={
                        "blockchain": blockchain,
                        "gas_price": gas_price,
                        "block_number": block_number
                    }
                )
            elif gas_price > thresholds["warning"]:
                return await self._create_event(
                    wallet_id=UUID("00000000-0000-0000-0000-000000000000"),
                    event_type=MonitorEventType.GAS_PRICE,
                    severity=MonitorSeverity.WARNING,
                    title="Prix du gaz élevé",
                    description=f"Prix du gaz à {gas_price} GWEI",
                    data={
                        "blockchain": blockchain,
                        "gas_price": gas_price,
                        "block_number": block_number
                    }
                )

            return None

        except Exception as e:
            logger.error(f"Erreur lors du monitoring du réseau: {e}")
            return None

    async def _get_network_gas_price(self, blockchain: str) -> float:
        """
        Récupère le prix du gaz du réseau.

        Args:
            blockchain: Blockchain

        Returns:
            Prix du gaz en GWEI
        """
        # Implémentation simplifiée
        return 30.0  # Valeur par défaut

    async def _get_network_block(self, blockchain: str) -> int:
        """
        Récupère le numéro de bloc du réseau.

        Args:
            blockchain: Blockchain

        Returns:
            Numéro de bloc
        """
        # Implémentation simplifiée
        return 0

    # ========================================================================
    # CRÉATION D'ÉVÉNEMENTS
    # ========================================================================

    async def _create_event(
        self,
        wallet_id: UUID,
        event_type: MonitorEventType,
        severity: MonitorSeverity,
        title: str,
        description: str,
        data: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> MonitorEvent:
        """
        Crée un événement de monitoring.

        Args:
            wallet_id: ID du wallet
            event_type: Type d'événement
            severity: Niveau de sévérité
            title: Titre
            description: Description
            data: Données supplémentaires
            metadata: Métadonnées

        Returns:
            Événement créé
        """
        event = MonitorEvent(
            event_id=uuid4(),
            wallet_id=wallet_id,
            event_type=event_type,
            severity=severity,
            title=title,
            description=description,
            data=data or {},
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        # Stockage
        if wallet_id not in self._event_cache:
            self._event_cache[wallet_id] = []
        
        self._event_cache[wallet_id].append(event)
        
        # Mise à jour des métriques
        self._metrics["total_events"] += 1
        event_type_key = event_type.value
        if event_type_key not in self._metrics["events_by_type"]:
            self._metrics["events_by_type"][event_type_key] = 0
        self._metrics["events_by_type"][event_type_key] += 1
        self._metrics["last_event"] = datetime.now().isoformat()

        # Notification
        await self._send_notification(event)

        return event

    # ========================================================================
    # ALERTES
    # ========================================================================

    async def _trigger_alert(
        self,
        wallet_id: UUID,
        alert_type: str,
        value: Any,
        metadata: Optional[Dict] = None
    ) -> Optional[MonitorAlert]:
        """
        Déclenche une alerte.

        Args:
            wallet_id: ID du wallet
            alert_type: Type d'alerte
            value: Valeur actuelle
            metadata: Métadonnées

        Returns:
            Alerte déclenchée ou None
        """
        try:
            # Récupération des configurations
            configs = await self.get_alert_configs(wallet_id)
            
            for config in configs:
                if config.get("condition_type") != alert_type:
                    continue

                # Vérification de la condition
                threshold = Decimal(str(config["threshold"]))
                condition = config["condition"]
                
                triggered = False
                if condition == ">":
                    triggered = value > threshold
                elif condition == ">=":
                    triggered = value >= threshold
                elif condition == "<":
                    triggered = value < threshold
                elif condition == "<=":
                    triggered = value <= threshold
                elif condition == "==":
                    triggered = value == threshold

                if triggered:
                    alert = MonitorAlert(
                        alert_id=uuid4(),
                        wallet_id=wallet_id,
                        user_id=UUID(config.get("user_id", "00000000-0000-0000-0000-000000000000")),
                        condition=condition,
                        threshold=float(threshold),
                        current_value=float(value),
                        severity=MonitorSeverity(config.get("severity", "warning")),
                        message=config.get("message", f"Alerte {alert_type} déclenchée"),
                        triggered_at=datetime.now(),
                        metadata=metadata or {}
                    )

                    # Stockage
                    if wallet_id not in self._alert_cache:
                        self._alert_cache[wallet_id] = []
                    
                    self._alert_cache[wallet_id].append(alert)
                    
                    # Mise à jour des métriques
                    self._metrics["total_alerts"] += 1
                    severity_key = alert.severity.value
                    if severity_key not in self._metrics["alerts_by_severity"]:
                        self._metrics["alerts_by_severity"][severity_key] = 0
                    self._metrics["alerts_by_severity"][severity_key] += 1
                    self._metrics["last_alert"] = datetime.now().isoformat()

                    # Notification
                    await self._send_alert_notification(alert)

                    return alert

            return None

        except Exception as e:
            logger.error(f"Erreur lors du déclenchement de l'alerte: {e}")
            return None

    # ========================================================================
    # VÉRIFICATIONS INTERNES
    # ========================================================================

    async def _check_balance_thresholds(
        self,
        wallet_id: UUID,
        balance_usd: Decimal
    ) -> Optional[MonitorEvent]:
        """
        Vérifie les seuils de solde.

        Args:
            wallet_id: ID du wallet
            balance_usd: Solde en USD

        Returns:
            Événement ou None
        """
        thresholds = self.DEFAULT_THRESHOLDS["balance"]
        
        if balance_usd < Decimal(str(thresholds["emergency"])):
            return await self._create_event(
                wallet_id=wallet_id,
                event_type=MonitorEventType.THRESHOLD,
                severity=MonitorSeverity.EMERGENCY,
                title="Solde critique",
                description=f"Le solde est de ${balance_usd:.2f} - niveau critique",
                data={"balance_usd": str(balance_usd)}
            )
        elif balance_usd < Decimal(str(thresholds["critical"])):
            return await self._create_event(
                wallet_id=wallet_id,
                event_type=MonitorEventType.THRESHOLD,
                severity=MonitorSeverity.CRITICAL,
                title="Solde très bas",
                description=f"Le solde est de ${balance_usd:.2f} - niveau critique",
                data={"balance_usd": str(balance_usd)}
            )
        elif balance_usd < Decimal(str(thresholds["warning"])):
            return await self._create_event(
                wallet_id=wallet_id,
                event_type=MonitorEventType.THRESHOLD,
                severity=MonitorSeverity.WARNING,
                title="Solde bas",
                description=f"Le solde est de ${balance_usd:.2f}",
                data={"balance_usd": str(balance_usd)}
            )

        return None

    async def _check_activity(
        self,
        wallet_id: UUID,
        transactions: List[Transaction]
    ) -> Optional[MonitorEvent]:
        """
        Vérifie l'activité du wallet.

        Args:
            wallet_id: ID du wallet
            transactions: Liste des transactions

        Returns:
            Événement ou None
        """
        # Vérification des transactions en 24h
        now = datetime.now()
        last_24h = [t for t in transactions if (now - t.timestamp).days < 1]
        
        if len(last_24h) > self.DEFAULT_THRESHOLDS["transaction_count"]["critical"]:
            return await self._create_event(
                wallet_id=wallet_id,
                event_type=MonitorEventType.THRESHOLD,
                severity=MonitorSeverity.CRITICAL,
                title="Activité anormalement élevée",
                description=f"{len(last_24h)} transactions en 24h",
                data={"transaction_count": len(last_24h)}
            )
        elif len(last_24h) > self.DEFAULT_THRESHOLDS["transaction_count"]["warning"]:
            return await self._create_event(
                wallet_id=wallet_id,
                event_type=MonitorEventType.THRESHOLD,
                severity=MonitorSeverity.WARNING,
                title="Activité élevée",
                description=f"{len(last_24h)} transactions en 24h",
                data={"transaction_count": len(last_24h)}
            )

        # Vérification de l'inactivité
        if transactions:
            last_tx = max(t.timestamp for t in transactions)
            days_inactive = (now - last_tx).days
            
            if days_inactive > 30:
                return await self._create_event(
                    wallet_id=wallet_id,
                    event_type=MonitorEventType.THRESHOLD,
                    severity=MonitorSeverity.INFO,
                    title="Wallet inactif",
                    description=f"Wallet inactif depuis {days_inactive} jours",
                    data={"days_inactive": days_inactive}
                )

        return None

    async def _update_metrics(
        self,
        wallet_id: UUID,
        transactions: List[Transaction],
        balance: WalletBalance
    ) -> None:
        """
        Met à jour les métriques du wallet.

        Args:
            wallet_id: ID du wallet
            transactions: Liste des transactions
            balance: Solde du wallet
        """
        try:
            # Calcul des métriques
            total_tx = len(transactions)
            total_volume = sum(t.amount_usd for t in transactions)
            
            # Succès/échec
            success_count = sum(1 for t in transactions if t.status == TransactionStatus.CONFIRMED)
            failed_count = sum(1 for t in transactions if t.status == TransactionStatus.FAILED)
            
            success_rate = success_count / total_tx if total_tx > 0 else 0
            
            # Dernières 24h
            now = datetime.now()
            last_24h = [t for t in transactions if (now - t.timestamp).days < 1]
            
            # Métriques
            metrics = MonitorMetrics(
                wallet_id=wallet_id,
                total_transactions=total_tx,
                total_volume_usd=total_volume,
                average_tx_value_usd=total_volume / total_tx if total_tx > 0 else Decimal("0"),
                max_tx_value_usd=max((t.amount_usd for t in transactions), default=Decimal("0")),
                tx_count_last_24h=len(last_24h),
                tx_count_last_7d=len([t for t in transactions if (now - t.timestamp).days < 7]),
                active_addresses=1,  # À implémenter
                unique_contracts=0,  # À implémenter
                success_rate=success_rate,
                error_rate=1 - success_rate,
                average_confirmation_time=0,  # À implémenter
                uptime_percentage=100.0,  # À implémenter
                last_block=0,  # À implémenter
                last_sync=datetime.now()
            )

            self._metrics_cache[wallet_id] = metrics

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des métriques: {e}")

    # ========================================================================
    # NOTIFICATIONS
    # ========================================================================

    async def _send_notification(self, event: MonitorEvent) -> None:
        """
        Envoie une notification pour un événement.

        Args:
            event: Événement à notifier
        """
        try:
            if event.severity in [MonitorSeverity.CRITICAL, MonitorSeverity.EMERGENCY]:
                # Notification critique
                await self._send_webhook_notification(event)
                
                # Notification par email (simulée)
                logger.info(f"📧 Email envoyé pour l'événement {event.event_id}")

            self._metrics["total_notifications"] += 1

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification: {e}")

    async def _send_alert_notification(self, alert: MonitorAlert) -> None:
        """
        Envoie une notification pour une alerte.

        Args:
            alert: Alerte à notifier
        """
        try:
            if alert.severity in [MonitorSeverity.CRITICAL, MonitorSeverity.EMERGENCY]:
                await self._send_webhook_alert(alert)

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification d'alerte: {e}")

    async def _send_webhook_notification(self, event: MonitorEvent) -> None:
        """
        Envoie une notification webhook.

        Args:
            event: Événement à envoyer
        """
        try:
            webhook_url = self.webhook_urls.get("critical")
            if not webhook_url:
                return

            async with aiohttp.ClientSession() as session:
                await session.post(
                    webhook_url,
                    json=event.to_dict()
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du webhook: {e}")

    async def _send_webhook_alert(self, alert: MonitorAlert) -> None:
        """
        Envoie une alerte webhook.

        Args:
            alert: Alerte à envoyer
        """
        try:
            webhook_url = self.webhook_urls.get("alert")
            if not webhook_url:
                return

            async with aiohttp.ClientSession() as session:
                await session.post(
                    webhook_url,
                    json=alert.to_dict()
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'alerte webhook: {e}")

    # ========================================================================
    # RÉCUPÉRATION DES DONNÉES
    # ========================================================================

    async def get_events(
        self,
        wallet_id: UUID,
        event_type: Optional[MonitorEventType] = None,
        severity: Optional[MonitorSeverity] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[MonitorEvent]:
        """
        Récupère les événements d'un wallet.

        Args:
            wallet_id: ID du wallet
            event_type: Filtrer par type
            severity: Filtrer par sévérité
            from_date: Date de début
            to_date: Date de fin
            limit: Nombre d'événements
            offset: Décalage

        Returns:
            Liste des événements
        """
        try:
            events = self._event_cache.get(wallet_id, [])
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            if severity:
                events = [e for e in events if e.severity == severity]
            
            if from_date:
                events = [e for e in events if e.timestamp >= from_date]
            
            if to_date:
                events = [e for e in events if e.timestamp <= to_date]
            
            events.sort(key=lambda x: x.timestamp, reverse=True)
            
            return events[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des événements: {e}")
            return []

    async def get_alerts(
        self,
        wallet_id: UUID,
        severity: Optional[MonitorSeverity] = None,
        acknowledged: Optional[bool] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[MonitorAlert]:
        """
        Récupère les alertes d'un wallet.

        Args:
            wallet_id: ID du wallet
            severity: Filtrer par sévérité
            acknowledged: Filtrer par acknowledgement
            resolved: Filtrer par résolution
            limit: Nombre d'alertes
            offset: Décalage

        Returns:
            Liste des alertes
        """
        try:
            alerts = self._alert_cache.get(wallet_id, [])
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            if acknowledged is not None:
                alerts = [a for a in alerts if a.acknowledged == acknowledged]
            
            if resolved is not None:
                alerts = [a for a in alerts if a.resolved == resolved]
            
            alerts.sort(key=lambda x: x.triggered_at, reverse=True)
            
            return alerts[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des alertes: {e}")
            return []

    async def get_metrics(
        self,
        wallet_id: UUID
    ) -> Optional[MonitorMetrics]:
        """
        Récupère les métriques d'un wallet.

        Args:
            wallet_id: ID du wallet

        Returns:
            Métriques du wallet
        """
        return self._metrics_cache.get(wallet_id)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def acknowledge_event(
        self,
        event_id: UUID
    ) -> bool:
        """
        Marque un événement comme reconnu.

        Args:
            event_id: ID de l'événement

        Returns:
            True si l'événement a été reconnu
        """
        for events in self._event_cache.values():
            for event in events:
                if event.event_id == event_id:
                    event.acknowledged = True
                    return True
        return False

    async def acknowledge_alert(
        self,
        alert_id: UUID
    ) -> bool:
        """
        Marque une alerte comme reconnue.

        Args:
            alert_id: ID de l'alerte

        Returns:
            True si l'alerte a été reconnue
        """
        for alerts in self._alert_cache.values():
            for alert in alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_at = datetime.now()
                    return True
        return False

    async def resolve_alert(
        self,
        alert_id: UUID
    ) -> bool:
        """
        Marque une alerte comme résolue.

        Args:
            alert_id: ID de l'alerte

        Returns:
            True si l'alerte a été résolue
        """
        for alerts in self._alert_cache.values():
            for alert in alerts:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    return True
        return False

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_events": self._metrics["total_events"],
                "total_alerts": self._metrics["total_alerts"],
                "total_notifications": self._metrics["total_notifications"],
                "events_by_type": self._metrics["events_by_type"],
                "alerts_by_severity": self._metrics["alerts_by_severity"],
                "last_event": self._metrics["last_event"],
                "last_alert": self._metrics["last_alert"],
                "cached_events": sum(len(e) for e in self._event_cache.values()),
                "cached_alerts": sum(len(a) for a in self._alert_cache.values()),
                "cached_metrics": len(self._metrics_cache),
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
        logger.info("Fermeture de WalletMonitor...")
        self._event_cache.clear()
        self._alert_cache.clear()
        self._metrics_cache.clear()
        self._alert_configs.clear()
        self._wallet_state.clear()
        logger.info("WalletMonitor fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_monitor(
    redis_url: str = "redis://localhost:6379/0",
    webhook_urls: Optional[Dict[str, str]] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> WalletMonitor:
    """
    Crée une instance du service de monitoring.

    Args:
        redis_url: URL de connexion Redis
        webhook_urls: URLs des webhooks
        api_keys: Clés API

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletMonitor(
        redis_client=redis_client,
        webhook_urls=webhook_urls,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "MonitorEventType",
    "MonitorSeverity",
    "MonitorEvent",
    "MonitorAlert",
    "MonitorMetrics",
    "WalletMonitor",
    "create_wallet_monitor"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de monitoring."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET MONITOR MODULE")
    print("=" * 60)

    # Création du service
    monitor = create_wallet_monitor(
        webhook_urls={
            "critical": "https://webhook.example.com/critical",
            "alert": "https://webhook.example.com/alert"
        }
    )

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Monitor Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Configuration d'une alerte
    alert_config = {
        "condition_type": "balance",
        "condition": "<",
        "threshold": 100,
        "severity": "warning",
        "message": "Solde bas - moins de 100 USD",
        "user_id": str(user_id)
    }
    
    await monitor.set_alert_config(wallet.config.wallet_id, alert_config)
    print(f"\n🔔 Alerte configurée: solde < 100 USD")

    # Monitoring de l'activité
    events = await monitor.monitor_wallet_activity(wallet)
    print(f"\n📊 Événements générés: {len(events)}")

    # Monitoring des prix
    price_events = await monitor.monitor_prices(["ethereum", "bitcoin"])
    print(f"\n📈 Événements de prix: {len(price_events)}")

    # Récupération des événements
    all_events = await monitor.get_events(wallet.config.wallet_id)
    print(f"\n📋 Tous les événements: {len(all_events)}")

    # Récupération des métriques
    metrics = await monitor.get_metrics(wallet.config.wallet_id)
    if metrics:
        print(f"\n📊 Métriques:")
        print(f"   Transactions: {metrics.total_transactions}")
        print(f"   Volume: ${metrics.total_volume_usd:.2f}")
        print(f"   Taux de succès: {metrics.success_rate*100:.1f}%")

    # Santé du service
    health = await monitor.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Événements: {health['total_events']}")
    print(f"   Alertes: {health['total_alerts']}")
    print(f"   Notifications: {health['total_notifications']}")

    # Fermeture
    await monitor.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletMonitor NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

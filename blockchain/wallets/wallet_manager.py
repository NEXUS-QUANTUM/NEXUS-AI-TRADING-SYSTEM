"""
NEXUS AI TRADING SYSTEM - WALLET MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion centralisée des wallets multi-blockchain.
Support de la création, gestion, surveillance et orchestration des wallets.

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
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import redis.asyncio as redis

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

from .ethereum_wallet import EthereumWallet, create_ethereum_wallet
from .bsc_wallet import BSCWallet, create_bsc_wallet
from .polygon_wallet import PolygonWallet, create_polygon_wallet
from .solana_wallet import SolanaWallet, create_solana_wallet
from .tron_wallet import TronWallet, create_tron_wallet
from .multi_chain_wallet import MultiChainWalletManager, ChainType

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class WalletManagerStatus(Enum):
    """Statuts du gestionnaire de wallets."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class WalletOperation(Enum):
    """Opérations sur les wallets."""
    CREATE = "create"
    DELETE = "delete"
    UPDATE = "update"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    IMPORT = "import"
    EXPORT = "export"
    BACKUP = "backup"
    RESTORE = "restore"


@dataclass
class WalletOperationResult:
    """Résultat d'une opération sur un wallet."""
    operation: WalletOperation
    wallet_id: UUID
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "operation": self.operation.value,
            "wallet_id": str(self.wallet_id),
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class WalletHealthCheck:
    """Résultat d'un health check sur un wallet."""
    wallet_id: UUID
    status: str
    is_healthy: bool
    balance: Optional[Decimal] = None
    balance_usd: Optional[Decimal] = None
    last_transaction: Optional[datetime] = None
    transaction_count: int = 0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "status": self.status,
            "is_healthy": self.is_healthy,
            "balance": str(self.balance) if self.balance else None,
            "balance_usd": str(self.balance_usd) if self.balance_usd else None,
            "last_transaction": self.last_transaction.isoformat() if self.last_transaction else None,
            "transaction_count": self.transaction_count,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET MANAGER
# ============================================================================

class WalletManager:
    """
    Gestionnaire centralisé de wallets multi-blockchain.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de wallets.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API pour les services externes
            config: Configuration du gestionnaire
        """
        self.redis_url = redis_url
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Clients
        self.redis = None
        self._session = None
        
        # Wallets actifs
        self._wallets: Dict[UUID, BaseWallet] = {}
        self._wallet_configs: Dict[UUID, WalletConfig] = {}
        
        # Multi-chain manager
        self.multi_chain_manager = None
        
        # Statut
        self.status = WalletManagerStatus.INITIALIZING
        
        # Métriques
        self._metrics = {
            "total_wallets": 0,
            "active_wallets": 0,
            "total_transactions": 0,
            "total_volume_usd": Decimal("0"),
            "by_chain": {},
            "by_type": {},
            "by_status": {},
            "health_checks": 0,
            "failed_health_checks": 0
        }
        
        # Health check cache
        self._health_cache: Dict[UUID, WalletHealthCheck] = {}
        
        # Compteurs d'opérations
        self._operation_counter = 0

        logger.info("WalletManager initialisé avec succès")

    # ========================================================================
    # INITIALISATION
    # ========================================================================

    async def initialize(self) -> bool:
        """
        Initialise le gestionnaire de wallets.

        Returns:
            True si l'initialisation a réussi
        """
        try:
            self.status = WalletManagerStatus.INITIALIZING
            
            # Connexion Redis
            self.redis = redis.Redis.from_url(self.redis_url)
            await self.redis.ping()
            
            # Session HTTP
            self._session = aiohttp.ClientSession()
            
            # Initialisation du multi-chain manager
            self.multi_chain_manager = MultiChainWalletManager(
                api_keys=self.api_keys,
                redis_client=self.redis
            )
            
            # Chargement des wallets depuis Redis
            await self._load_wallets()
            
            self.status = WalletManagerStatus.RUNNING
            logger.info("WalletManager initialisé avec succès")
            return True

        except Exception as e:
            self.status = WalletManagerStatus.ERROR
            logger.error(f"Erreur d'initialisation du WalletManager: {e}")
            return False

    async def _load_wallets(self) -> None:
        """
        Charge les wallets depuis Redis.
        """
        try:
            # Récupération des IDs de wallets
            wallet_ids = await self.redis.smembers("nexus:wallets:all")
            
            for wallet_id_bytes in wallet_ids:
                wallet_id = UUID(wallet_id_bytes.decode())
                config_data = await self.redis.get(f"nexus:wallet:{wallet_id}")
                
                if config_data:
                    config_dict = json.loads(config_data)
                    config = self._config_from_dict(config_dict)
                    self._wallet_configs[wallet_id] = config
            
            logger.info(f"{len(self._wallet_configs)} wallets chargés depuis Redis")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des wallets: {e}")

    # ========================================================================
    # CRÉATION DE WALLETS
    # ========================================================================

    async def create_wallet(
        self,
        user_id: UUID,
        name: str,
        blockchain: str,
        network: BlockchainNetwork,
        wallet_type: WalletType = WalletType.EOA,
        private_key: Optional[str] = None,
        mnemonic: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> WalletOperationResult:
        """
        Crée un nouveau wallet.

        Args:
            user_id: ID de l'utilisateur
            name: Nom du wallet
            blockchain: Blockchain
            network: Réseau
            wallet_type: Type de wallet
            private_key: Clé privée (optionnel)
            mnemonic: Phrase mnémonique (optionnel)
            metadata: Métadonnées

        Returns:
            Résultat de l'opération
        """
        try:
            wallet_id = uuid4()
            self._operation_counter += 1

            # Création du wallet selon la blockchain
            wallet = None
            blockchain_lower = blockchain.lower()

            if blockchain_lower == "ethereum":
                wallet = create_ethereum_wallet(
                    user_id=user_id,
                    name=name,
                    network=network,
                    private_key=private_key,
                    mnemonic=mnemonic,
                    api_keys=self.api_keys
                )
            elif blockchain_lower == "bsc":
                wallet = create_bsc_wallet(
                    user_id=user_id,
                    name=name,
                    network=network,
                    private_key=private_key,
                    mnemonic=mnemonic,
                    api_keys=self.api_keys
                )
            elif blockchain_lower == "polygon":
                wallet = create_polygon_wallet(
                    user_id=user_id,
                    name=name,
                    network=network,
                    private_key=private_key,
                    mnemonic=mnemonic,
                    api_keys=self.api_keys
                )
            elif blockchain_lower == "solana":
                wallet = create_solana_wallet(
                    user_id=user_id,
                    name=name,
                    network=network,
                    private_key=private_key,
                    mnemonic=mnemonic,
                    api_keys=self.api_keys
                )
            elif blockchain_lower == "tron":
                wallet = create_tron_wallet(
                    user_id=user_id,
                    name=name,
                    network=network,
                    private_key=private_key,
                    mnemonic=mnemonic,
                    api_keys=self.api_keys
                )
            else:
                raise ValueError(f"Blockchain non supportée: {blockchain}")

            # Initialisation du wallet
            await wallet.initialize()

            # Stockage
            self._wallets[wallet_id] = wallet
            self._wallet_configs[wallet_id] = wallet.config

            # Sauvegarde dans Redis
            await self._save_wallet(wallet_id)

            # Mise à jour des métriques
            self._metrics["total_wallets"] += 1
            self._metrics["active_wallets"] += 1
            if blockchain_lower not in self._metrics["by_chain"]:
                self._metrics["by_chain"][blockchain_lower] = 0
            self._metrics["by_chain"][blockchain_lower] += 1

            # Mise à jour du multi-chain manager
            chain_type = self._get_chain_type(blockchain_lower)
            if chain_type:
                await self.multi_chain_manager.add_chain_to_wallet(
                    wallet_id=wallet_id,
                    chain=chain_type,
                    private_key=private_key,
                    mnemonic=mnemonic
                )

            return WalletOperationResult(
                operation=WalletOperation.CREATE,
                wallet_id=wallet_id,
                success=True,
                message=f"Wallet {name} créé avec succès",
                data={
                    "wallet": wallet.config.to_dict(),
                    "address": wallet.config.address
                },
                metadata=metadata or {}
            )

        except Exception as e:
            logger.error(f"Erreur lors de la création du wallet: {e}")
            return WalletOperationResult(
                operation=WalletOperation.CREATE,
                wallet_id=wallet_id if 'wallet_id' in locals() else uuid4(),
                success=False,
                message=f"Erreur de création: {str(e)}",
                metadata=metadata or {}
            )

    async def _save_wallet(self, wallet_id: UUID) -> None:
        """
        Sauvegarde un wallet dans Redis.

        Args:
            wallet_id: ID du wallet
        """
        try:
            if wallet_id in self._wallet_configs:
                config = self._wallet_configs[wallet_id]
                config_dict = self._config_to_dict(config)
                
                await self.redis.setex(
                    f"nexus:wallet:{wallet_id}",
                    86400 * 30,  # 30 jours
                    json.dumps(config_dict)
                )
                
                await self.redis.sadd("nexus:wallets:all", str(wallet_id))
                
                # Index par utilisateur
                await self.redis.sadd(
                    f"nexus:wallets:user:{config.user_id}",
                    str(wallet_id)
                )
                
                # Index par blockchain
                await self.redis.sadd(
                    f"nexus:wallets:chain:{config.blockchain}",
                    str(wallet_id)
                )

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du wallet: {e}")

    # ========================================================================
    # GESTION DES WALLETS
    # ========================================================================

    async def get_wallet(
        self,
        wallet_id: UUID
    ) -> Optional[BaseWallet]:
        """
        Récupère un wallet par son ID.

        Args:
            wallet_id: ID du wallet

        Returns:
            Wallet ou None
        """
        # Vérification du cache
        if wallet_id in self._wallets:
            return self._wallets[wallet_id]

        # Chargement depuis Redis
        config_data = await self.redis.get(f"nexus:wallet:{wallet_id}")
        if config_data:
            config_dict = json.loads(config_data)
            config = self._config_from_dict(config_dict)
            
            # Création du wallet
            wallet = self._create_wallet_from_config(config)
            if wallet:
                await wallet.initialize()
                self._wallets[wallet_id] = wallet
                return wallet

        return None

    async def get_wallets(
        self,
        user_id: Optional[UUID] = None,
        blockchain: Optional[str] = None,
        status: Optional[WalletStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[BaseWallet]:
        """
        Récupère la liste des wallets.

        Args:
            user_id: Filtrer par utilisateur
            blockchain: Filtrer par blockchain
            status: Filtrer par statut
            limit: Nombre de wallets
            offset: Décalage

        Returns:
            Liste des wallets
        """
        try:
            if user_id:
                wallet_ids = await self.redis.smembers(
                    f"nexus:wallets:user:{user_id}"
                )
            elif blockchain:
                wallet_ids = await self.redis.smembers(
                    f"nexus:wallets:chain:{blockchain}"
                )
            else:
                wallet_ids = await self.redis.smembers("nexus:wallets:all")

            wallets = []
            for wallet_id_bytes in list(wallet_ids)[offset:offset + limit]:
                wallet_id = UUID(wallet_id_bytes.decode())
                wallet = await self.get_wallet(wallet_id)
                if wallet:
                    if status and wallet.config.status != status:
                        continue
                    wallets.append(wallet)

            return wallets

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des wallets: {e}")
            return []

    async def delete_wallet(
        self,
        wallet_id: UUID,
        permanent: bool = False
    ) -> WalletOperationResult:
        """
        Supprime un wallet.

        Args:
            wallet_id: ID du wallet
            permanent: Suppression définitive

        Returns:
            Résultat de l'opération
        """
        try:
            self._operation_counter += 1

            if wallet_id not in self._wallets:
                return WalletOperationResult(
                    operation=WalletOperation.DELETE,
                    wallet_id=wallet_id,
                    success=False,
                    message="Wallet non trouvé"
                )

            wallet = self._wallets[wallet_id]
            
            # Fermeture du wallet
            await wallet.close()

            # Suppression
            del self._wallets[wallet_id]
            del self._wallet_configs[wallet_id]

            if permanent:
                await self.redis.delete(f"nexus:wallet:{wallet_id}")
                await self.redis.srem("nexus:wallets:all", str(wallet_id))
                await self.redis.srem(
                    f"nexus:wallets:user:{wallet.config.user_id}",
                    str(wallet_id)
                )
                await self.redis.srem(
                    f"nexus:wallets:chain:{wallet.config.blockchain}",
                    str(wallet_id)
                )

            # Mise à jour des métriques
            self._metrics["total_wallets"] -= 1
            if wallet.config.status == WalletStatus.ACTIVE:
                self._metrics["active_wallets"] -= 1

            return WalletOperationResult(
                operation=WalletOperation.DELETE,
                wallet_id=wallet_id,
                success=True,
                message="Wallet supprimé avec succès"
            )

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du wallet: {e}")
            return WalletOperationResult(
                operation=WalletOperation.DELETE,
                wallet_id=wallet_id,
                success=False,
                message=f"Erreur de suppression: {str(e)}"
            )

    async def freeze_wallet(
        self,
        wallet_id: UUID
    ) -> WalletOperationResult:
        """
        Gèle un wallet.

        Args:
            wallet_id: ID du wallet

        Returns:
            Résultat de l'opération
        """
        try:
            self._operation_counter += 1

            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return WalletOperationResult(
                    operation=WalletOperation.FREEZE,
                    wallet_id=wallet_id,
                    success=False,
                    message="Wallet non trouvé"
                )

            wallet.config.status = WalletStatus.FROZEN
            await self._save_wallet(wallet_id)

            return WalletOperationResult(
                operation=WalletOperation.FREEZE,
                wallet_id=wallet_id,
                success=True,
                message="Wallet gelé avec succès"
            )

        except Exception as e:
            logger.error(f"Erreur lors du gel du wallet: {e}")
            return WalletOperationResult(
                operation=WalletOperation.FREEZE,
                wallet_id=wallet_id,
                success=False,
                message=f"Erreur de gel: {str(e)}"
            )

    async def unfreeze_wallet(
        self,
        wallet_id: UUID
    ) -> WalletOperationResult:
        """
        Dégèle un wallet.

        Args:
            wallet_id: ID du wallet

        Returns:
            Résultat de l'opération
        """
        try:
            self._operation_counter += 1

            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return WalletOperationResult(
                    operation=WalletOperation.UNFREEZE,
                    wallet_id=wallet_id,
                    success=False,
                    message="Wallet non trouvé"
                )

            wallet.config.status = WalletStatus.ACTIVE
            await self._save_wallet(wallet_id)

            return WalletOperationResult(
                operation=WalletOperation.UNFREEZE,
                wallet_id=wallet_id,
                success=True,
                message="Wallet dégelé avec succès"
            )

        except Exception as e:
            logger.error(f"Erreur lors du dégel du wallet: {e}")
            return WalletOperationResult(
                operation=WalletOperation.UNFREEZE,
                wallet_id=wallet_id,
                success=False,
                message=f"Erreur de dégel: {str(e)}"
            )

    # ========================================================================
    # SURVEILLANCE ET HEALTH CHECK
    # ========================================================================

    async def health_check(
        self,
        wallet_id: UUID,
        force_refresh: bool = False
    ) -> WalletHealthCheck:
        """
        Effectue un health check sur un wallet.

        Args:
            wallet_id: ID du wallet
            force_refresh: Forcer le rafraîchissement

        Returns:
            Résultat du health check
        """
        try:
            # Vérification du cache
            if not force_refresh and wallet_id in self._health_cache:
                cached = self._health_cache[wallet_id]
                if (datetime.now() - cached.timestamp).seconds < 60:
                    return cached

            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return WalletHealthCheck(
                    wallet_id=wallet_id,
                    status="not_found",
                    is_healthy=False,
                    error_message="Wallet non trouvé"
                )

            try:
                # Récupération du solde
                balance = await wallet.get_balance()
                
                # Récupération des transactions récentes
                transactions = await wallet.get_transactions(limit=10)
                
                # Dernière transaction
                last_tx = max(
                    (t for t in transactions if t.status == TransactionStatus.CONFIRMED),
                    key=lambda t: t.timestamp,
                    default=None
                )

                health = WalletHealthCheck(
                    wallet_id=wallet_id,
                    status="healthy",
                    is_healthy=True,
                    balance=balance.native_balance,
                    balance_usd=balance.total_balance_usd,
                    last_transaction=last_tx.timestamp if last_tx else None,
                    transaction_count=len(transactions),
                    timestamp=datetime.now()
                )

                self._health_cache[wallet_id] = health
                self._metrics["health_checks"] += 1

                return health

            except Exception as e:
                self._metrics["failed_health_checks"] += 1
                return WalletHealthCheck(
                    wallet_id=wallet_id,
                    status="error",
                    is_healthy=False,
                    error_message=str(e),
                    timestamp=datetime.now()
                )

        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            return WalletHealthCheck(
                wallet_id=wallet_id,
                status="error",
                is_healthy=False,
                error_message=str(e)
            )

    async def health_check_all(
        self,
        force_refresh: bool = False
    ) -> Dict[UUID, WalletHealthCheck]:
        """
        Effectue un health check sur tous les wallets.

        Args:
            force_refresh: Forcer le rafraîchissement

        Returns:
            Dictionnaire des résultats de health check
        """
        results = {}
        
        for wallet_id in list(self._wallets.keys()):
            result = await self.health_check(wallet_id, force_refresh)
            results[wallet_id] = result

        return results

    async def monitor_wallets(
        self,
        interval_seconds: int = 60
    ) -> None:
        """
        Surveille en continu les wallets.

        Args:
            interval_seconds: Intervalle de surveillance
        """
        try:
            while self.status == WalletManagerStatus.RUNNING:
                await self.health_check_all()
                await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            logger.info("Surveillance des wallets arrêtée")
        except Exception as e:
            logger.error(f"Erreur lors de la surveillance des wallets: {e}")

    # ========================================================================
    # STATISTIQUES ET RAPPORTS
    # ========================================================================

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Récupère les statistiques du gestionnaire.

        Returns:
            Statistiques
        """
        try:
            # Mise à jour des statistiques
            for wallet in self._wallets.values():
                chain = wallet.config.blockchain
                if chain not in self._metrics["by_chain"]:
                    self._metrics["by_chain"][chain] = 0
                self._metrics["by_chain"][chain] += 1

                wallet_type = wallet.config.type.value
                if wallet_type not in self._metrics["by_type"]:
                    self._metrics["by_type"][wallet_type] = 0
                self._metrics["by_type"][wallet_type] += 1

                status = wallet.config.status.value
                if status not in self._metrics["by_status"]:
                    self._metrics["by_status"][status] = 0
                self._metrics["by_status"][status] += 1

            return {
                **self._metrics,
                "status": self.status.value,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return {}

    async def get_dashboard_data(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère les données pour le tableau de bord.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Données du tableau de bord
        """
        try:
            wallets = await self.get_wallets(user_id=user_id)
            
            total_balance = Decimal("0")
            total_transactions = 0
            
            for wallet in wallets:
                balance = await wallet.get_balance()
                total_balance += balance.total_balance_usd
                
                txs = await wallet.get_transactions(limit=100)
                total_transactions += len(txs)

            return {
                "user_id": str(user_id),
                "total_wallets": len(wallets),
                "total_balance_usd": float(total_balance),
                "total_transactions": total_transactions,
                "wallets": [
                    {
                        "id": str(w.config.wallet_id),
                        "name": w.config.name,
                        "blockchain": w.config.blockchain,
                        "address": w.config.address[:8] + "..." + w.config.address[-8:],
                        "status": w.config.status.value
                    }
                    for w in wallets
                ],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données du tableau de bord: {e}")
            return {}

    # ========================================================================
    # MÉTHODES D'EXPORT ET IMPORT
    # ========================================================================

    async def export_wallet(
        self,
        wallet_id: UUID,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Exporte un wallet.

        Args:
            wallet_id: ID du wallet
            format: Format d'export

        Returns:
            Données exportées
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return {"error": "Wallet non trouvé"}

            config = wallet.config.to_dict()
            
            if format == "json":
                return config
            elif format == "keystore":
                if hasattr(wallet, 'export_keystore'):
                    return await wallet.export_keystore(self.config.get("keystore_password", ""))
                return {"error": "Keystore non supporté"}
            else:
                return {"error": f"Format non supporté: {format}"}

        except Exception as e:
            logger.error(f"Erreur lors de l'export du wallet: {e}")
            return {"error": str(e)}

    async def import_wallet(
        self,
        data: Dict[str, Any],
        user_id: UUID,
        name: str,
        password: Optional[str] = None
    ) -> WalletOperationResult:
        """
        Importe un wallet.

        Args:
            data: Données à importer
            user_id: ID de l'utilisateur
            name: Nom du wallet
            password: Mot de passe (pour keystore)

        Returns:
            Résultat de l'opération
        """
        try:
            self._operation_counter += 1

            # Détection du format
            if "address" in data and "private_key_encrypted" in data:
                # Format JSON standard
                blockchain = data.get("blockchain", "ethereum")
                network = data.get("network", "mainnet")
                private_key = data.get("private_key_encrypted")
                
                return await self.create_wallet(
                    user_id=user_id,
                    name=name,
                    blockchain=blockchain,
                    network=BlockchainNetwork(network),
                    private_key=private_key
                )

            elif "version" in data and "crypto" in data:
                # Format Keystore
                if not password:
                    return WalletOperationResult(
                        operation=WalletOperation.IMPORT,
                        wallet_id=uuid4(),
                        success=False,
                        message="Mot de passe requis pour le keystore"
                    )
                
                from eth_account import Account
                account = Account.decrypt(data, password)
                private_key = account.key.hex()
                address = account.address
                
                return await self.create_wallet(
                    user_id=user_id,
                    name=name,
                    blockchain="ethereum",
                    network=BlockchainNetwork.ETHEREUM_MAINNET,
                    private_key=private_key
                )

            else:
                return WalletOperationResult(
                    operation=WalletOperation.IMPORT,
                    wallet_id=uuid4(),
                    success=False,
                    message="Format de données non reconnu"
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'import du wallet: {e}")
            return WalletOperationResult(
                operation=WalletOperation.IMPORT,
                wallet_id=uuid4(),
                success=False,
                message=f"Erreur d'import: {str(e)}"
            )

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    def _get_chain_type(self, blockchain: str) -> Optional[ChainType]:
        """
        Récupère le type de chaîne pour le multi-chain manager.

        Args:
            blockchain: Nom de la blockchain

        Returns:
            Type de chaîne
        """
        chain_map = {
            "ethereum": ChainType.ETHEREUM,
            "bsc": ChainType.BSC,
            "polygon": ChainType.POLYGON,
            "solana": ChainType.SOLANA,
            "avalanche": ChainType.AVALANCHE,
            "arbitrum": ChainType.ARBITRUM,
            "optimism": ChainType.OPTIMISM
        }
        return chain_map.get(blockchain.lower())

    def _config_from_dict(self, data: Dict[str, Any]) -> WalletConfig:
        """
        Crée une configuration à partir d'un dictionnaire.

        Args:
            data: Données de configuration

        Returns:
            Configuration
        """
        return WalletConfig(
            wallet_id=UUID(data["wallet_id"]),
            user_id=UUID(data["user_id"]),
            name=data["name"],
            type=WalletType(data["type"]),
            blockchain=data["blockchain"],
            network=BlockchainNetwork(data["network"]),
            address=data["address"],
            private_key_encrypted=data.get("private_key_encrypted"),
            public_key=data.get("public_key"),
            mnemonic_encrypted=data.get("mnemonic_encrypted"),
            derivation_path=data.get("derivation_path"),
            is_hardware=data.get("is_hardware", False),
            is_imported=data.get("is_imported", False),
            is_created=data.get("is_created", True),
            status=WalletStatus(data.get("status", "active")),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now()
        )

    def _config_to_dict(self, config: WalletConfig) -> Dict[str, Any]:
        """
        Convertit une configuration en dictionnaire.

        Args:
            config: Configuration

        Returns:
            Dictionnaire
        """
        return {
            "wallet_id": str(config.wallet_id),
            "user_id": str(config.user_id),
            "name": config.name,
            "type": config.type.value,
            "blockchain": config.blockchain,
            "network": config.network.value,
            "address": config.address,
            "private_key_encrypted": config.private_key_encrypted,
            "public_key": config.public_key,
            "mnemonic_encrypted": config.mnemonic_encrypted,
            "derivation_path": config.derivation_path,
            "is_hardware": config.is_hardware,
            "is_imported": config.is_imported,
            "is_created": config.is_created,
            "status": config.status.value,
            "metadata": config.metadata,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat()
        }

    def _create_wallet_from_config(
        self,
        config: WalletConfig
    ) -> Optional[BaseWallet]:
        """
        Crée un wallet à partir d'une configuration.

        Args:
            config: Configuration

        Returns:
            Wallet créé
        """
        blockchain = config.blockchain.lower()
        
        if blockchain == "ethereum":
            return EthereumWallet(config, self.api_keys)
        elif blockchain == "bsc":
            return BSCWallet(config, self.api_keys)
        elif blockchain == "polygon":
            return PolygonWallet(config, self.api_keys)
        elif blockchain == "solana":
            return SolanaWallet(config, self.api_keys)
        elif blockchain == "tron":
            return TronWallet(config, self.api_keys)
        else:
            return None

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du gestionnaire.

        Returns:
            État de santé
        """
        try:
            stats = await self.get_statistics()
            
            # Vérification de Redis
            redis_healthy = False
            if self.redis:
                try:
                    await self.redis.ping()
                    redis_healthy = True
                except Exception:
                    pass

            return {
                "status": "healthy" if self.status == WalletManagerStatus.RUNNING else self.status.value,
                "redis": redis_healthy,
                "wallets": {
                    "total": stats.get("total_wallets", 0),
                    "active": stats.get("active_wallets", 0)
                },
                "metrics": self._metrics,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le gestionnaire."""
        logger.info("Fermeture de WalletManager...")
        
        self.status = WalletManagerStatus.STOPPED
        
        # Fermeture des wallets
        for wallet in self._wallets.values():
            try:
                await wallet.close()
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture du wallet: {e}")
        
        self._wallets.clear()
        self._wallet_configs.clear()
        
        # Fermeture du multi-chain manager
        if self.multi_chain_manager:
            await self.multi_chain_manager.close()
        
        # Fermeture de Redis
        if self.redis:
            await self.redis.close()
        
        # Fermeture de la session HTTP
        if self._session:
            await self._session.close()
        
        logger.info("WalletManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> WalletManager:
    """
    Crée une instance du gestionnaire de wallets.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API pour les services externes
        config: Configuration du gestionnaire

    Returns:
        Instance du gestionnaire
    """
    return WalletManager(
        redis_url=redis_url,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "WalletManagerStatus",
    "WalletOperation",
    "WalletOperationResult",
    "WalletHealthCheck",
    "WalletManager",
    "create_wallet_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire de wallets."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET MANAGER MODULE")
    print("=" * 60)

    # Création du gestionnaire
    manager = create_wallet_manager(
        redis_url="redis://localhost:6379/0",
        api_keys={
            "etherscan": "YOUR_ETHERSCAN_API_KEY",
            "bscscan": "YOUR_BSCSCAN_API_KEY"
        }
    )

    # Initialisation
    await manager.initialize()
    print(f"\n✅ WalletManager initialisé: {manager.status.value}")

    # Création d'un wallet
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    result = await manager.create_wallet(
        user_id=user_id,
        name="Main Ethereum Wallet",
        blockchain="ethereum",
        network=BlockchainNetwork.ETHEREUM_MAINNET
    )

    print(f"\n📦 Création du wallet:")
    print(f"   ID: {result.wallet_id}")
    print(f"   Succès: {result.success}")
    print(f"   Message: {result.message}")
    if result.data:
        print(f"   Adresse: {result.data.get('address', 'N/A')[:8]}...")

    # Récupération des wallets
    wallets = await manager.get_wallets(user_id=user_id)
    print(f"\n📋 Wallets de l'utilisateur: {len(wallets)}")

    if wallets:
        wallet = wallets[0]
        
        # Health check
        health = await manager.health_check(wallet.config.wallet_id)
        print(f"\n❤️ Health check:")
        print(f"   Statut: {health.status}")
        print(f"   Sain: {health.is_healthy}")
        if health.balance:
            print(f"   Solde: {health.balance:.4f} ETH")
        if health.balance_usd:
            print(f"   Solde USD: ${health.balance_usd:.2f}")

        # Gel du wallet
        freeze_result = await manager.freeze_wallet(wallet.config.wallet_id)
        print(f"\n❄️ Gel du wallet:")
        print(f"   Succès: {freeze_result.success}")
        print(f"   Message: {freeze_result.message}")

        # Dégel du wallet
        unfreeze_result = await manager.unfreeze_wallet(wallet.config.wallet_id)
        print(f"\n🔥 Dégel du wallet:")
        print(f"   Succès: {unfreeze_result.success}")
        print(f"   Message: {unfreeze_result.message}")

    # Statistiques
    stats = await manager.get_statistics()
    print(f"\n📊 Statistiques:")
    print(f"   Total wallets: {stats.get('total_wallets', 0)}")
    print(f"   Wallets actifs: {stats.get('active_wallets', 0)}")
    print(f"   Health checks: {stats.get('health_checks', 0)}")

    # Santé du gestionnaire
    health = await manager.get_health()
    print(f"\n❤️ Santé du gestionnaire:")
    print(f"   Statut: {health['status']}")
    print(f"   Redis: {health['redis']}")

    # Fermeture
    await manager.close()

    print("\n" + "=" * 60)
    print("WalletManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

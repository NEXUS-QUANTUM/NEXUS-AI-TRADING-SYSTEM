# blockchain/nft/nft_manager.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Manager - Gestionnaire Centralisé NFT

Ce module implémente un gestionnaire centralisé pour toutes les opérations NFT,
intégrant les marketplaces, les collections, les prêts, et l'analytique
dans une interface unifiée.

Fonctionnalités principales:
- Interface unifiée pour toutes les opérations NFT
- Gestion centralisée des collections
- Trading sur multiples marketplaces
- Prêts NFT
- Analytique avancée
- Monitoring en temps réel
- Alertes de marché
- Support multi-chain
"""

import asyncio
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

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTMetadata, NFTStandard, NFTStatus
    from .nft_config import NFTConfigManager, NFTEnvironment, NFTMarketplace, NFTChain
    from .erc721 import ERC721Manager
    from .erc1155 import ERC1155Manager
    from .blur import BlurIntegration
    from .looksrare import LooksRareIntegration
    from .nft_lending import NFTLendingManager
    from .nft_analytics import NFTAnalytics
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTMetadata, NFTStandard, NFTStatus
    from .nft_config import NFTConfigManager, NFTEnvironment, NFTMarketplace, NFTChain
    from .erc721 import ERC721Manager
    from .erc1155 import ERC1155Manager
    from .blur import BlurIntegration
    from .looksrare import LooksRareIntegration
    from .nft_lending import NFTLendingManager
    from .nft_analytics import NFTAnalytics

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NFTManagerStatus(Enum):
    """Statuts du gestionnaire NFT"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class NFTManagerConfig:
    """Configuration du gestionnaire NFT"""
    auto_monitor: bool = True
    max_positions: int = 100
    max_listings: int = 50
    min_floor_price: Decimal = Decimal("0.01")
    max_risk_score: float = 0.7
    monitor_interval: int = 300  # 5 minutes
    trading_enabled: bool = True
    lending_enabled: bool = True
    max_slippage: Decimal = Decimal("0.01")
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NFTManagerState:
    """État du gestionnaire NFT"""
    status: NFTManagerStatus
    total_collections: int
    total_nfts: int
    total_value_usd: Decimal
    total_listings: int
    active_loans: int
    risk_score: float
    last_update: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "status": self.status.value,
            "total_collections": self.total_collections,
            "total_nfts": self.total_nfts,
            "total_value_usd": str(self.total_value_usd),
            "total_listings": self.total_listings,
            "active_loans": self.active_loans,
            "risk_score": self.risk_score,
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTManager:
    """
    Gestionnaire centralisé NFT
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Any],
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire NFT

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # Configuration
        self.manager_config = NFTManagerConfig(**config.get("manager", {}))

        # États internes
        self._status = NFTManagerStatus.INITIALIZING
        self._state: Optional[NFTManagerState] = None
        self._nfts: Dict[str, NFTData] = {}
        self._collections: Dict[str, NFTCollection] = {}
        self._listings: Dict[str, NFTListing] = {}
        self._loans: Dict[str, NFTLoan] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._is_running = False
        self._monitor_tasks: List[asyncio.Task] = []

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Initialisation des sous-systèmes
        self._initialize_subsystems()

        # Chargement de l'état
        self._load_state()

        self._status = NFTManagerStatus.ACTIVE

        logger.info("NFTManager initialisé avec succès")

    # ============================================================
    # INITIALISATION
    # ============================================================

    def _initialize_subsystems(self) -> None:
        """Initialise les sous-systèmes NFT"""
        try:
            # Configuration
            self.config_manager = NFTConfigManager(
                config_dir=self.config.get("config_dir"),
                environment=self.config.get("environment", "production"),
                metrics_collector=self.metrics,
            )

            # Gestionnaires de standards
            self.erc721_manager = ERC721Manager(
                config=self.config.get("erc721", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            self.erc1155_manager = ERC1155Manager(
                config=self.config.get("erc1155", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            # Marketplaces
            self.blur_integration = BlurIntegration(
                config=self.config.get("blur", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            self.looksrare_integration = LooksRareIntegration(
                config=self.config.get("looksrare", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            # Lending
            self.lending_manager = NFTLendingManager(
                config=self.config.get("lending", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            # Analytics
            nft_instances = {
                "ethereum_erc721": self.erc721_manager,
                "ethereum_erc1155": self.erc1155_manager,
            }
            self.analytics = NFTAnalytics(
                config=self.config.get("analytics", {}),
                nft_instances=nft_instances,
                metrics_collector=self.metrics,
            )

            # Ajout des callbacks d'alerte
            self.blur_integration.add_alert_callback(self._handle_alert)
            self.looksrare_integration.add_alert_callback(self._handle_alert)
            self.lending_manager.add_alert_callback(self._handle_alert)

            logger.info("Sous-systèmes NFT initialisés")

        except Exception as e:
            logger.error(f"Erreur d'initialisation des sous-systèmes: {e}")
            raise NFTError(f"Erreur d'initialisation: {e}")

    def _load_state(self) -> None:
        """Charge l'état du gestionnaire"""
        self._state = NFTManagerState(
            status=NFTManagerStatus.ACTIVE,
            total_collections=0,
            total_nfts=0,
            total_value_usd=Decimal("0"),
            total_listings=0,
            active_loans=0,
            risk_score=0.0,
            last_update=None,
        )

        # Chargement des collections configurées
        for collection_id, collection_config in self.config_manager.get_config().collections.items():
            self._collections[collection_id] = NFTCollection(
                collection_id=collection_id,
                name=collection_config.name,
                symbol=collection_config.symbol,
                contract_address=collection_config.contract_address,
                chain=collection_config.chain,
                standard=collection_config.standard,
                total_supply=collection_config.total_supply,
                floor_price=collection_config.floor_price,
                volume_24h=Decimal("0"),
                volume_total=Decimal("0"),
                items_count=collection_config.total_supply,
                owners_count=0,
                created_at=collection_config.created_at,
                updated_at=collection_config.updated_at,
                metadata=collection_config.metadata,
            )

        logger.info(f"État NFTManager chargé: {len(self._collections)} collections")

    # ============================================================
    # MÉTHODES PUBLIQUES - COLLECTIONS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_collection(
        self,
        collection_id: str,
        force_refresh: bool = False,
    ) -> Optional[NFTCollection]:
        """
        Obtient une collection NFT

        Args:
            collection_id: ID de la collection
            force_refresh: Forcer le rafraîchissement

        Returns:
            Collection NFT ou None
        """
        try:
            collection = self._collections.get(collection_id)
            if not collection:
                # Recherche par adresse
                collection_config = self.config_manager.get_collection(collection_id)
                if not collection_config:
                    return None

                collection = NFTCollection(
                    collection_id=collection_config.collection_id,
                    name=collection_config.name,
                    symbol=collection_config.symbol,
                    contract_address=collection_config.contract_address,
                    chain=collection_config.chain,
                    standard=collection_config.standard,
                    total_supply=collection_config.total_supply,
                    floor_price=collection_config.floor_price,
                    volume_24h=Decimal("0"),
                    volume_total=Decimal("0"),
                    items_count=collection_config.total_supply,
                    owners_count=0,
                    created_at=collection_config.created_at,
                    updated_at=collection_config.updated_at,
                    metadata=collection_config.metadata,
                )
                self._collections[collection_id] = collection

            if force_refresh:
                # Mise à jour des données
                updated_collection = await self._update_collection_data(collection)
                if updated_collection:
                    collection = updated_collection
                    self._collections[collection_id] = collection

            return collection

        except Exception as e:
            logger.error(f"Erreur de récupération de la collection: {e}")
            raise NFTError(f"Erreur de récupération de la collection: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_nft(
        self,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
        force_refresh: bool = False,
    ) -> Optional[NFTData]:
        """
        Obtient un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            NFT ou None
        """
        try:
            # Détermination du standard
            standard = await self._detect_standard(contract_address, chain)

            if standard == NFTStandard.ERC721:
                return await self.erc721_manager.get_nft(contract_address, token_id, chain=chain)
            elif standard == NFTStandard.ERC1155:
                return await self.erc1155_manager.get_nft(contract_address, token_id, chain=chain)
            else:
                raise NFTError(f"Standard {standard} non supporté")

        except Exception as e:
            logger.error(f"Erreur de récupération du NFT: {e}")
            raise NFTError(f"Erreur de récupération du NFT: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - TRADING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def list_nft(
        self,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        marketplace: NFTMarketplace = NFTMarketplace.BLUR,
        currency: str = "ETH",
        duration: int = 86400,
    ) -> str:
        """
        Liste un NFT sur une marketplace

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de vente
            wallet_address: Adresse du wallet
            marketplace: Marketplace
            currency: Devise
            duration: Durée de la listing

        Returns:
            Hash de la transaction
        """
        logger.info(f"Listing NFT sur {marketplace.value}")

        try:
            # Vérification de l'état
            if not self.manager_config.trading_enabled:
                raise NFTError("Trading désactivé")

            # Récupération du NFT
            nft = await self.get_nft(contract_address, token_id)
            if not nft:
                raise NFTError("NFT non trouvé")

            # Vérification du propriétaire
            if nft.owner.lower() != wallet_address.lower():
                raise NFTError("Vous n'êtes pas le propriétaire du NFT")

            # Listing sur la marketplace
            if marketplace == NFTMarketplace.BLUR:
                result = await self.blur_integration.list_nft(
                    contract_address=contract_address,
                    token_id=token_id,
                    price=price,
                    wallet_address=wallet_address,
                    currency=currency,
                    duration=duration,
                )
            elif marketplace == NFTMarketplace.LOOKSRARE:
                result = await self.looksrare_integration.list_nft(
                    contract_address=contract_address,
                    token_id=token_id,
                    price=price,
                    wallet_address=wallet_address,
                    currency=currency,
                    duration=duration,
                )
            else:
                raise NFTError(f"Marketplace {marketplace.value} non supportée")

            # Métriques
            self.metrics.record_increment(
                "nft_listing",
                1,
                {"marketplace": marketplace.value},
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de listing: {e}")
            raise NFTError(f"Erreur de listing: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def buy_nft(
        self,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        marketplace: NFTMarketplace = NFTMarketplace.BLUR,
        currency: str = "ETH",
    ) -> str:
        """
        Achète un NFT sur une marketplace

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix d'achat
            wallet_address: Adresse du wallet
            marketplace: Marketplace
            currency: Devise

        Returns:
            Hash de la transaction
        """
        logger.info(f"Achat NFT sur {marketplace.value}")

        try:
            if not self.manager_config.trading_enabled:
                raise NFTError("Trading désactivé")

            if marketplace == NFTMarketplace.BLUR:
                result = await self.blur_integration.buy_nft(
                    contract_address=contract_address,
                    token_id=token_id,
                    price=price,
                    wallet_address=wallet_address,
                    currency=currency,
                )
            elif marketplace == NFTMarketplace.LOOKSRARE:
                result = await self.looksrare_integration.buy_nft(
                    contract_address=contract_address,
                    token_id=token_id,
                    price=price,
                    wallet_address=wallet_address,
                    currency=currency,
                )
            else:
                raise NFTError(f"Marketplace {marketplace.value} non supportée")

            self.metrics.record_increment(
                "nft_buy",
                1,
                {"marketplace": marketplace.value},
            )

            return result

        except Exception as e:
            logger.error(f"Erreur d'achat: {e}")
            raise NFTError(f"Erreur d'achat: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - LENDING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def lend_nft(
        self,
        contract_address: str,
        token_id: str,
        amount: Decimal,
        wallet_address: str,
        interest_rate: Decimal = Decimal("0.1"),
        duration: int = 86400,
    ) -> NFTLoan:
        """
        Prête un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            amount: Montant du prêt
            wallet_address: Adresse du wallet
            interest_rate: Taux d'intérêt
            duration: Durée

        Returns:
            Prêt créé
        """
        try:
            if not self.manager_config.lending_enabled:
                raise NFTError("Lending désactivé")

            return await self.lending_manager.offer_loan(
                protocol=NFTLendingProtocol.BLUR,
                contract_address=contract_address,
                token_id=token_id,
                amount=amount,
                wallet_address=wallet_address,
                interest_rate=interest_rate,
                duration=duration,
            )

        except Exception as e:
            logger.error(f"Erreur de prêt: {e}")
            raise NFTError(f"Erreur de prêt: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def borrow_against_nft(
        self,
        contract_address: str,
        token_id: str,
        amount: Decimal,
        wallet_address: str,
    ) -> NFTLoan:
        """
        Emprunte contre un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            amount: Montant de l'emprunt
            wallet_address: Adresse du wallet

        Returns:
            Prêt créé
        """
        try:
            if not self.manager_config.lending_enabled:
                raise NFTError("Lending désactivé")

            # Recherche d'une offre de prêt existante
            loans = await self.lending_manager.get_loans_by_lender(
                self._get_default_lender()
            )

            for loan in loans:
                if (loan.contract_address.lower() == contract_address.lower() and
                    loan.token_id == token_id and
                    loan.status == NFTLoanStatus.PENDING):
                    # Acceptation du prêt
                    await self.lending_manager.accept_loan(
                        loan_id=loan.loan_id,
                        wallet_address=wallet_address,
                    )
                    return loan

            raise NFTError("Aucune offre de prêt disponible")

        except Exception as e:
            logger.error(f"Erreur d'emprunt: {e}")
            raise NFTError(f"Erreur d'emprunt: {e}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring en arrière-plan"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage du monitoring NFT")

        # Tâches de monitoring
        self._monitor_tasks.extend([
            asyncio.create_task(self._monitor_collections()),
            asyncio.create_task(self._monitor_listings()),
            asyncio.create_task(self._monitor_loans()),
            asyncio.create_task(self._monitor_market()),
        ])

        # Démarrer le monitoring des sous-systèmes
        await self.blur_integration.monitor_collections()
        await self.lending_manager.monitor_loans()

        # Monitoring de l'analytique
        asyncio.create_task(self._monitor_analytics())

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
        logger.info("Monitoring NFT arrêté")

    async def _monitor_collections(self) -> None:
        """Monitore les collections en continu"""
        while self._is_running:
            try:
                for collection_id in self._collections:
                    await self.get_collection(collection_id, force_refresh=True)

                # Mise à jour de l'état
                await self._update_state()

            except Exception as e:
                logger.error(f"Erreur de monitoring des collections: {e}")

            await asyncio.sleep(self.manager_config.monitor_interval)

    async def _monitor_listings(self) -> None:
        """Monitore les listings en continu"""
        while self._is_running:
            try:
                # Vérification des listings expirés
                for listing_id, listing in list(self._listings.items()):
                    if listing.expires_at and listing.expires_at < datetime.now():
                        listing.status = NFTStatus.EXPIRED
                        await self._send_alert({
                            "type": "listing_expired",
                            "listing_id": listing_id,
                            "severity": "info",
                        })

            except Exception as e:
                logger.error(f"Erreur de monitoring des listings: {e}")

            await asyncio.sleep(60)

    async def _monitor_loans(self) -> None:
        """Monitore les prêts en continu"""
        while self._is_running:
            try:
                for loan_id, loan in list(self._loans.items()):
                    if loan.status == NFTLoanStatus.ACTIVE:
                        # Vérification du temps restant
                        if loan.end_time < datetime.now():
                            loan.status = NFTLoanStatus.EXPIRED
                            await self._send_alert({
                                "type": "loan_expired",
                                "loan_id": loan_id,
                                "severity": "warning",
                            })

            except Exception as e:
                logger.error(f"Erreur de monitoring des prêts: {e}")

            await asyncio.sleep(60)

    async def _monitor_market(self) -> None:
        """Monitore le marché en continu"""
        while self._is_running:
            try:
                # Analyse des tendances du marché
                overview = await self.analytics.get_market_overview()

                # Alertes sur les tendances
                if Decimal(overview["total_volume_24h"]) > 0:
                    self.metrics.record_gauge(
                        "nft_market_volume",
                        float(overview["total_volume_24h"]),
                    )

            except Exception as e:
                logger.error(f"Erreur de monitoring du marché: {e}")

            await asyncio.sleep(self.manager_config.monitor_interval * 2)

    async def _monitor_analytics(self) -> None:
        """Monitore l'analytique en continu"""
        while self._is_running:
            try:
                # Mise à jour des métriques
                for collection_id in self._collections:
                    analytics = await self.analytics.get_collection_analytics(
                        collection_id,
                        force_refresh=True,
                    )

                    self.metrics.record_gauge(
                        "nft_collection_floor_price",
                        float(analytics.floor_price),
                        {"collection": collection_id},
                    )
                    self.metrics.record_gauge(
                        "nft_collection_volume",
                        float(analytics.volume_24h),
                        {"collection": collection_id},
                    )

            except Exception as e:
                logger.error(f"Erreur de monitoring de l'analytique: {e}")

            await asyncio.sleep(self.manager_config.monitor_interval * 3)

    # ============================================================
    # MÉTHODES D'ANALYSE
    # ============================================================

    @async_retry(max_attempts=2, initial_delay=1.0)
    async def get_market_overview(self) -> Dict[str, Any]:
        """
        Obtient une vue d'ensemble du marché NFT

        Returns:
            Vue d'ensemble du marché
        """
        return await self.analytics.get_market_overview()

    @async_retry(max_attempts=2, initial_delay=1.0)
    async def generate_report(
        self,
        title: str,
        timeframe: str = "week",
        collections: Optional[List[str]] = None,
    ) -> NFTReport:
        """
        Génère un rapport NFT

        Args:
            title: Titre du rapport
            timeframe: Période
            collections: Collections à analyser

        Returns:
            Rapport NFT
        """
        # Conversion du timeframe
        timeframe_map = {
            "hour": NFTAnalyticsTimeframe.HOUR,
            "day": NFTAnalyticsTimeframe.DAY,
            "week": NFTAnalyticsTimeframe.WEEK,
            "month": NFTAnalyticsTimeframe.MONTH,
            "quarter": NFTAnalyticsTimeframe.QUARTER,
            "year": NFTAnalyticsTimeframe.YEAR,
        }
        tf = timeframe_map.get(timeframe, NFTAnalyticsTimeframe.WEEK)

        return await self.analytics.generate_report(
            title=title,
            timeframe=tf,
            collections=collections,
        )

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    async def _update_state(self) -> None:
        """Met à jour l'état du gestionnaire"""
        try:
            # Calcul des métriques
            total_collections = len(self._collections)
            total_nfts = len(self._nfts)
            total_listings = len(self._listings)
            active_loans = len([l for l in self._loans.values() if l.status == NFTLoanStatus.ACTIVE])

            # Calcul de la valeur totale
            total_value = Decimal("0")
            for collection in self._collections.values():
                total_value += collection.floor_price * collection.total_supply

            # Score de risque
            risk_score = self._calculate_risk_score()

            # Mise à jour de l'état
            if self._state:
                self._state.total_collections = total_collections
                self._state.total_nfts = total_nfts
                self._state.total_value_usd = total_value
                self._state.total_listings = total_listings
                self._state.active_loans = active_loans
                self._state.risk_score = risk_score
                self._state.last_update = datetime.now()
                self._state.status = self._status

            # Métriques
            self.metrics.record_gauge("nft_total_value", float(total_value))
            self.metrics.record_gauge("nft_risk_score", risk_score)

        except Exception as e:
            logger.error(f"Erreur de mise à jour de l'état: {e}")

    def _calculate_risk_score(self) -> float:
        """Calcule le score de risque"""
        if not self._collections:
            return 0.0

        # Facteurs de risque
        risk_factors = []

        # Concentration
        total_value = sum(c.floor_price * c.total_supply for c in self._collections.values())
        if total_value > 0:
            for collection in self._collections.values():
                concentration = (collection.floor_price * collection.total_supply) / total_value
                if concentration > 0.3:
                    risk_factors.append(0.7)
                elif concentration > 0.2:
                    risk_factors.append(0.5)
                else:
                    risk_factors.append(0.3)

        # Volatilité (simulée)
        risk_factors.append(0.4)

        # Score moyen
        return sum(risk_factors) / len(risk_factors) if risk_factors else 0.0

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _detect_standard(self, contract_address: str, chain: str) -> NFTStandard:
        """Détecte le standard d'un contrat"""
        try:
            # Essayer ERC-721
            try:
                await self.erc721_manager.get_owner(contract_address, "1", chain=chain)
                return NFTStandard.ERC721
            except Exception:
                pass

            # Essayer ERC-1155
            try:
                await self.erc1155_manager.get_balance(contract_address, "1", "0x...", chain=chain)
                return NFTStandard.ERC1155
            except Exception:
                pass

            return NFTStandard.ERC721

        except Exception:
            return NFTStandard.ERC721

    async def _update_collection_data(
        self,
        collection: NFTCollection,
    ) -> Optional[NFTCollection]:
        """Met à jour les données d'une collection"""
        # Simulé
        return collection

    def _get_default_lender(self) -> str:
        """Obtient l'adresse du prêteur par défaut"""
        # Dans la réalité, on utiliserait une adresse configurée
        return "0x0000000000000000000000000000000000000000"

    async def _handle_alert(self, alert: Dict[str, Any]) -> None:
        """Gère une alerte"""
        logger.info(f"Alerte NFT: {alert}")

        self.metrics.record_increment(
            "nft_alert",
            1,
            {"type": alert.get("type", "unknown"), "severity": alert.get("severity", "info")},
        )

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        await self._handle_alert(alert)

    # ============================================================
    # MÉTHODES DE CONTROLE
    # ============================================================

    def pause(self) -> None:
        """Met en pause le gestionnaire"""
        self._status = NFTManagerStatus.PAUSED
        logger.info("NFTManager mis en pause")

    def resume(self) -> None:
        """Reprend le gestionnaire"""
        self._status = NFTManagerStatus.ACTIVE
        logger.info("NFTManager repris")

    def emergency_stop(self) -> None:
        """Arrêt d'urgence"""
        self._status = NFTManagerStatus.SHUTDOWN
        logger.warning("NFTManager arrêté d'urgence")

        asyncio.create_task(self._emergency_cleanup())

    async def _emergency_cleanup(self) -> None:
        """Nettoyage d'urgence"""
        try:
            await self.stop_monitoring()
            await self.erc721_manager.cleanup()
            await self.erc1155_manager.cleanup()
            await self.blur_integration.cleanup()
            await self.looksrare_integration.cleanup()
            await self.lending_manager.cleanup()
            await self.analytics.cleanup()
            await self.config_manager.cleanup()
            logger.info("Nettoyage d'urgence terminé")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage d'urgence: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        return {
            "status": self._status.value,
            "total_collections": len(self._collections),
            "total_nfts": len(self._nfts),
            "total_listings": len(self._listings),
            "active_loans": len([l for l in self._loans.values() if l.status == NFTLoanStatus.ACTIVE]),
            "risk_score": self._state.risk_score if self._state else 0.0,
            "is_running": self._is_running,
            "monitor_tasks": len(self._monitor_tasks),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTManager...")

        self._status = NFTManagerStatus.SHUTDOWN

        await self.stop_monitoring()

        await self.erc721_manager.cleanup()
        await self.erc1155_manager.cleanup()
        await self.blur_integration.cleanup()
        await self.looksrare_integration.cleanup()
        await self.lending_manager.cleanup()
        await self.analytics.cleanup()
        await self.config_manager.cleanup()

        self._nfts.clear()
        self._collections.clear()
        self._listings.clear()
        self._loans.clear()
        self._active_operations.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> NFTManager:
    """
    Crée une instance de NFTManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTManager
    """
    return NFTManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTManager"""
    # Configuration
    config = {
        "environment": "production",
        "manager": {
            "auto_monitor": True,
            "trading_enabled": True,
            "lending_enabled": True,
            "monitor_interval": 300,
        },
        "blur": {},
        "looksrare": {},
        "lending": {},
        "analytics": {},
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du gestionnaire
    manager = create_nft_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE NFT: {alert}")

    manager.add_alert_callback(alert_callback)

    # Démarrage du monitoring
    await manager.start_monitoring()

    # Obtention d'une collection
    collection = await manager.get_collection("bored_ape_yacht_club")
    print(f"Collection: {collection.to_dict() if collection else 'Non trouvée'}")

    # Obtention d'un NFT
    nft = await manager.get_nft(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
    )
    print(f"NFT: {nft.to_dict() if nft else 'Non trouvé'}")

    # Listing d'un NFT
    tx_hash = await manager.list_nft(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("50"),
        wallet_address="0x...",
    )
    print(f"Listing: {tx_hash}")

    # Vue d'ensemble du marché
    overview = await manager.get_market_overview()
    print(f"Vue d'ensemble du marché: {overview}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

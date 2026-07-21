"""
NEXUS AI TRADING SYSTEM - MULTI-CHAIN WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de wallet multi-blockchain pour la plateforme NEXUS.
Support unifié pour Ethereum, BSC, Polygon, Solana, Avalanche, Arbitrum, Optimism, etc.

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
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.middleware import geth_poa_middleware

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    TokenInfo,
    BlockchainNetwork,
    WalletStatus,
    WalletType,
    InsufficientBalanceError,
    InvalidAddressError,
    TransactionError,
    NetworkError
)

# Import des wallets spécifiques
from .ethereum_wallet import EthereumWallet, ERC20_TOKENS
from .bsc_wallet import BSCWallet, BEP20_TOKENS
from .polygon_wallet import PolygonWallet, POLYGON_TOKENS
from .solana_wallet import SolanaWallet, SPL_TOKENS

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES MULTI-CHAIN
# ============================================================================

class ChainType(Enum):
    """Types de blockchains supportées."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    SOLANA = "solana"
    AVALANCHE = "avalanche"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    CARDANO = "cardano"
    POLKADOT = "polkadot"
    COSMOS = "cosmos"
    TRON = "tron"
    NEAR = "near"
    APTOS = "aptos"
    SUI = "sui"

# Mapping des réseaux par blockchain
CHAIN_NETWORKS = {
    ChainType.ETHEREUM: [
        BlockchainNetwork.ETHEREUM_MAINNET,
        BlockchainNetwork.ETHEREUM_GOERLI,
        BlockchainNetwork.ETHEREUM_SEPOLIA
    ],
    ChainType.BSC: [
        BlockchainNetwork.BSC_MAINNET,
        BlockchainNetwork.BSC_TESTNET
    ],
    ChainType.POLYGON: [
        BlockchainNetwork.POLYGON_MAINNET,
        BlockchainNetwork.POLYGON_MUMBAI
    ],
    ChainType.SOLANA: [
        BlockchainNetwork.SOLANA_MAINNET,
        BlockchainNetwork.SOLANA_DEVNET,
        BlockchainNetwork.SOLANA_TESTNET
    ],
    ChainType.AVALANCHE: [
        BlockchainNetwork.AVALANCHE_MAINNET,
        BlockchainNetwork.AVALANCHE_FUJI
    ],
    ChainType.ARBITRUM: [
        BlockchainNetwork.ARBITRUM_MAINNET,
        BlockchainNetwork.ARBITRUM_GOERLI
    ],
    ChainType.OPTIMISM: [
        BlockchainNetwork.OPTIMISM_MAINNET,
        BlockchainNetwork.OPTIMISM_GOERLI
    ]
}

# Tokens populaires par blockchain
CHAIN_TOKENS = {
    ChainType.ETHEREUM: ERC20_TOKENS,
    ChainType.BSC: BEP20_TOKENS,
    ChainType.POLYGON: POLYGON_TOKENS,
    ChainType.SOLANA: SPL_TOKENS,
    ChainType.AVALANCHE: {
        "AVAX": {
            "address": "0x0000000000000000000000000000000000000000",
            "symbol": "AVAX",
            "name": "Avalanche",
            "decimals": 18
        },
        "USDC": {
            "address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
            "symbol": "USDC",
            "name": "USD Coin",
            "decimals": 6
        },
        "USDT": {
            "address": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
            "symbol": "USDT",
            "name": "Tether USD",
            "decimals": 6
        }
    },
    ChainType.ARBITRUM: {
        "ETH": {
            "address": "0x0000000000000000000000000000000000000000",
            "symbol": "ETH",
            "name": "Ethereum",
            "decimals": 18
        },
        "USDC": {
            "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            "symbol": "USDC",
            "name": "USD Coin",
            "decimals": 6
        },
        "USDT": {
            "address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
            "symbol": "USDT",
            "name": "Tether USD",
            "decimals": 6
        }
    },
    ChainType.OPTIMISM: {
        "ETH": {
            "address": "0x0000000000000000000000000000000000000000",
            "symbol": "ETH",
            "name": "Ethereum",
            "decimals": 18
        },
        "USDC": {
            "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
            "symbol": "USDC",
            "name": "USD Coin",
            "decimals": 6
        },
        "USDT": {
            "address": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
            "symbol": "USDT",
            "name": "Tether USD",
            "decimals": 6
        }
    }
}

# Configuration des bridges
BRIDGE_CONFIG = {
    "ethereum_to_arbitrum": {
        "source_chain": ChainType.ETHEREUM,
        "target_chain": ChainType.ARBITRUM,
        "bridge_address": "0x...",
        "gas_limit": 300000
    },
    "ethereum_to_optimism": {
        "source_chain": ChainType.ETHEREUM,
        "target_chain": ChainType.OPTIMISM,
        "bridge_address": "0x...",
        "gas_limit": 300000
    },
    "ethereum_to_polygon": {
        "source_chain": ChainType.ETHEREUM,
        "target_chain": ChainType.POLYGON,
        "bridge_address": "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf",
        "gas_limit": 500000
    },
    "bsc_to_ethereum": {
        "source_chain": ChainType.BSC,
        "target_chain": ChainType.ETHEREUM,
        "bridge_address": "0x...",
        "gas_limit": 300000
    }
}


# ============================================================================
# DATACLASSES MULTI-CHAIN
# ============================================================================

@dataclass
class MultiChainWallet:
    """Wallet multi-blockchain."""
    wallet_id: UUID
    user_id: UUID
    name: str
    chains: Dict[ChainType, WalletConfig]
    primary_chain: ChainType
    status: WalletStatus = WalletStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le wallet en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "chains": {k.value: v.to_dict() for k, v in self.chains.items()},
            "primary_chain": self.primary_chain.value,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class CrossChainTransaction:
    """Transaction cross-chain."""
    tx_id: UUID
    user_id: UUID
    source_chain: ChainType
    target_chain: ChainType
    source_tx: Transaction
    target_tx: Optional[Transaction] = None
    bridge_tx: Optional[Transaction] = None
    amount: Decimal = Decimal("0")
    amount_usd: Decimal = Decimal("0")
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la transaction en dictionnaire."""
        return {
            "tx_id": str(self.tx_id),
            "user_id": str(self.user_id),
            "source_chain": self.source_chain.value,
            "target_chain": self.target_chain.value,
            "source_tx": self.source_tx.to_dict() if self.source_tx else None,
            "target_tx": self.target_tx.to_dict() if self.target_tx else None,
            "bridge_tx": self.bridge_tx.to_dict() if self.bridge_tx else None,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


# ============================================================================
# CLASSE MULTI-CHAIN WALLET
# ============================================================================

class MultiChainWalletManager:
    """
    Gestionnaire de wallets multi-blockchain.
    Support unifié pour toutes les blockchains supportées.
    """

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        redis_client: Optional[Any] = None
    ):
        """
        Initialise le gestionnaire multi-chain.

        Args:
            api_keys: Clés API pour les services externes
            redis_client: Client Redis pour le cache
        """
        self.api_keys = api_keys or {}
        self.redis_client = redis_client
        
        # Cache des wallets
        self._wallet_cache: Dict[UUID, MultiChainWallet] = {}
        self._chain_wallet_cache: Dict[str, Dict[str, Any]] = {}
        self._transaction_cache: Dict[str, CrossChainTransaction] = {}
        
        # Instances des wallets spécifiques
        self._chain_wallets: Dict[str, Any] = {}
        
        # Métriques
        self._metrics = {
            "total_wallets": 0,
            "active_wallets": 0,
            "total_transactions": 0,
            "total_volume_usd": Decimal("0"),
            "by_chain": {}
        }

        logger.info("MultiChainWalletManager initialisé avec succès")

    # ========================================================================
    # GESTION DES WALLETS
    # ========================================================================

    async def create_wallet(
        self,
        user_id: UUID,
        name: str,
        chains: List[ChainType],
        primary_chain: Optional[ChainType] = None,
        private_keys: Optional[Dict[ChainType, str]] = None,
        mnemonics: Optional[Dict[ChainType, str]] = None,
        metadata: Optional[Dict] = None
    ) -> MultiChainWallet:
        """
        Crée un wallet multi-blockchain.

        Args:
            user_id: ID de l'utilisateur
            name: Nom du wallet
            chains: Liste des blockchains à inclure
            primary_chain: Blockchain principale
            private_keys: Clés privées par blockchain
            mnemonics: Phrases mnémoniques par blockchain
            metadata: Métadonnées supplémentaires

        Returns:
            Wallet multi-blockchain créé
        """
        try:
            wallet_id = uuid4()
            chain_configs = {}
            
            # Détermination de la blockchain principale
            if not primary_chain:
                primary_chain = chains[0] if chains else ChainType.ETHEREUM

            # Création des configurations par blockchain
            for chain in chains:
                chain_name = chain.value
                network = self._get_default_network(chain)
                
                # Création ou récupération de la clé privée
                private_key = None
                if private_keys and chain in private_keys:
                    private_key = private_keys[chain]
                elif mnemonics and chain in mnemonics:
                    # Dérivation de la clé privée depuis la mnémonique
                    private_key = await self._derive_private_key_from_mnemonic(
                        mnemonics[chain],
                        chain
                    )
                else:
                    # Génération d'une nouvelle clé privée
                    private_key = await self._generate_private_key(chain)

                # Création de la configuration
                config = WalletConfig(
                    wallet_id=wallet_id,
                    user_id=user_id,
                    name=f"{name} - {chain_name.upper()}",
                    type=WalletType.HD,
                    blockchain=chain_name,
                    network=network,
                    address="",  # Sera rempli par le wallet spécifique
                    private_key_encrypted=private_key,
                    is_created=True,
                    is_imported=bool(private_keys or mnemonics),
                    status=WalletStatus.ACTIVE,
                    metadata={"source": "nexus_multi_chain"}
                )
                
                chain_configs[chain] = config

            # Création du wallet multi-chain
            wallet = MultiChainWallet(
                wallet_id=wallet_id,
                user_id=user_id,
                name=name,
                chains=chain_configs,
                primary_chain=primary_chain,
                metadata=metadata or {}
            )

            # Initialisation des wallets spécifiques
            for chain, config in chain_configs.items():
                chain_wallet = await self._init_chain_wallet(chain, config)
                if chain_wallet:
                    # Récupération de l'adresse générée
                    await chain_wallet.initialize()
                    config.address = chain_wallet.config.address
                    self._chain_wallets[f"{wallet_id}_{chain.value}"] = chain_wallet

            # Mise en cache
            self._wallet_cache[wallet_id] = wallet
            self._metrics["total_wallets"] += 1
            self._metrics["active_wallets"] += 1

            logger.info(f"Wallet multi-chain créé: {wallet_id} pour {user_id}")
            return wallet

        except Exception as e:
            logger.error(f"Erreur lors de la création du wallet multi-chain: {e}")
            raise

    async def _init_chain_wallet(
        self,
        chain: ChainType,
        config: WalletConfig
    ) -> Optional[BaseWallet]:
        """
        Initialise un wallet spécifique pour une blockchain.

        Args:
            chain: Type de blockchain
            config: Configuration du wallet

        Returns:
            Wallet spécifique initialisé
        """
        try:
            if chain == ChainType.ETHEREUM:
                return EthereumWallet(config, self.api_keys)
            elif chain == ChainType.BSC:
                return BSCWallet(config, self.api_keys)
            elif chain == ChainType.POLYGON:
                return PolygonWallet(config, self.api_keys)
            elif chain == ChainType.SOLANA:
                return SolanaWallet(config, self.api_keys)
            elif chain == ChainType.AVALANCHE:
                # Importer et créer AvalancheWallet
                from .avalanche_wallet import AvalancheWallet
                return AvalancheWallet(config, self.api_keys)
            elif chain == ChainType.ARBITRUM:
                from .arbitrum_wallet import ArbitrumWallet
                return ArbitrumWallet(config, self.api_keys)
            elif chain == ChainType.OPTIMISM:
                from .optimism_wallet import OptimismWallet
                return OptimismWallet(config, self.api_keys)
            else:
                logger.warning(f"Blockchain {chain.value} non supportée")
                return None

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du wallet {chain.value}: {e}")
            return None

    async def get_wallet(
        self,
        wallet_id: UUID
    ) -> Optional[MultiChainWallet]:
        """
        Récupère un wallet multi-chain.

        Args:
            wallet_id: ID du wallet

        Returns:
            Wallet multi-chain ou None
        """
        try:
            # Vérification du cache
            if wallet_id in self._wallet_cache:
                return self._wallet_cache[wallet_id]

            # Récupération depuis la base de données
            # Pour l'exemple, nous retournons None
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du wallet: {e}")
            return None

    async def get_wallet_by_address(
        self,
        address: str,
        chain: ChainType
    ) -> Optional[MultiChainWallet]:
        """
        Récupère un wallet par adresse et blockchain.

        Args:
            address: Adresse du wallet
            chain: Blockchain

        Returns:
            Wallet multi-chain ou None
        """
        try:
            # Recherche dans le cache
            cache_key = f"{chain.value}_{address}"
            if cache_key in self._chain_wallet_cache:
                wallet_id = UUID(self._chain_wallet_cache[cache_key]["wallet_id"])
                return await self.get_wallet(wallet_id)

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du wallet par adresse: {e}")
            return None

    async def get_wallet_balance(
        self,
        wallet_id: UUID,
        chain: Optional[ChainType] = None,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, WalletBalance]:
        """
        Récupère le solde d'un wallet multi-chain.

        Args:
            wallet_id: ID du wallet
            chain: Blockchain spécifique (optionnel)
            token_address: Adresse du token (optionnel)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Dictionnaire des soldes par blockchain
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                raise ValueError(f"Wallet {wallet_id} non trouvé")

            balances = {}
            chains_to_check = [chain] if chain else list(wallet.chains.keys())

            for chain_type in chains_to_check:
                if chain_type not in wallet.chains:
                    continue

                chain_key = f"{wallet_id}_{chain_type.value}"
                if chain_key in self._chain_wallets:
                    chain_wallet = self._chain_wallets[chain_key]
                    
                    try:
                        balance = await chain_wallet.get_balance(
                            token_address=token_address,
                            force_refresh=force_refresh
                        )
                        balances[chain_type.value] = balance
                    except Exception as e:
                        logger.error(f"Erreur lors de la récupération du solde pour {chain_type.value}: {e}")

            return balances

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde: {e}")
            raise

    async def get_total_balance(
        self,
        wallet_id: UUID,
        include_tokens: bool = True
    ) -> Dict[str, Any]:
        """
        Récupère le solde total d'un wallet multi-chain.

        Args:
            wallet_id: ID du wallet
            include_tokens: Inclure les tokens

        Returns:
            Solde total
        """
        try:
            balances = await self.get_wallet_balance(wallet_id)
            
            total_native = Decimal("0")
            total_tokens = Decimal("0")
            total_usd = Decimal("0")
            
            chain_balances = {}

            for chain_name, balance in balances.items():
                chain_total = balance.total_balance_usd
                total_usd += chain_total
                
                chain_balances[chain_name] = {
                    "native": float(balance.native_balance),
                    "native_usd": float(balance.native_balance_usd),
                    "tokens": {k: float(v) for k, v in balance.token_balances.items()},
                    "tokens_usd": {k: float(v) for k, v in balance.token_balances_usd.items()},
                    "total_usd": float(chain_total)
                }

            return {
                "wallet_id": str(wallet_id),
                "total_usd": float(total_usd),
                "native_balance": float(total_native),
                "token_balance": float(total_tokens),
                "by_chain": chain_balances,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde total: {e}")
            return {}

    async def send_transaction(
        self,
        wallet_id: UUID,
        chain: ChainType,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        data: Optional[str] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Envoie une transaction sur une blockchain spécifique.

        Args:
            wallet_id: ID du wallet
            chain: Blockchain cible
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token
            data: Données de la transaction
            gas_price: Prix du gaz
            gas_limit: Limite de gaz
            metadata: Métadonnées

        Returns:
            Transaction envoyée
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                raise ValueError(f"Wallet {wallet_id} non trouvé")

            if chain not in wallet.chains:
                raise ValueError(f"Blockchain {chain.value} non configurée pour ce wallet")

            chain_key = f"{wallet_id}_{chain.value}"
            if chain_key not in self._chain_wallets:
                raise ValueError(f"Wallet pour {chain.value} non initialisé")

            chain_wallet = self._chain_wallets[chain_key]

            # Envoi de la transaction
            tx = await chain_wallet.send_transaction(
                to_address=to_address,
                amount=amount,
                token_address=token_address,
                data=data,
                gas_price=gas_price,
                gas_limit=gas_limit,
                metadata=metadata
            )

            # Mise à jour des métriques
            self._metrics["total_transactions"] += 1
            self._metrics["total_volume_usd"] += tx.amount_usd

            return tx

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la transaction: {e}")
            raise

    async def send_batch_transactions(
        self,
        wallet_id: UUID,
        transactions: List[Dict[str, Any]]
    ) -> List[Transaction]:
        """
        Envoie un lot de transactions.

        Args:
            wallet_id: ID du wallet
            transactions: Liste des transactions à envoyer

        Returns:
            Liste des transactions envoyées
        """
        results = []
        
        for tx_data in transactions:
            try:
                tx = await self.send_transaction(
                    wallet_id=wallet_id,
                    chain=tx_data.get("chain"),
                    to_address=tx_data.get("to_address"),
                    amount=tx_data.get("amount"),
                    token_address=tx_data.get("token_address"),
                    data=tx_data.get("data"),
                    gas_price=tx_data.get("gas_price"),
                    gas_limit=tx_data.get("gas_limit"),
                    metadata=tx_data.get("metadata")
                )
                results.append(tx)
            except Exception as e:
                logger.error(f"Erreur dans le lot de transactions: {e}")
                results.append(None)
        
        return results

    async def cross_chain_transfer(
        self,
        wallet_id: UUID,
        source_chain: ChainType,
        target_chain: ChainType,
        amount: Decimal,
        token_address: Optional[str] = None,
        recipient_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> CrossChainTransaction:
        """
        Effectue un transfert cross-chain.

        Args:
            wallet_id: ID du wallet
            source_chain: Blockchain source
            target_chain: Blockchain cible
            amount: Montant à transférer
            token_address: Adresse du token
            recipient_address: Adresse du destinataire (optionnel)
            metadata: Métadonnées

        Returns:
            Transaction cross-chain
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                raise ValueError(f"Wallet {wallet_id} non trouvé")

            # Vérification des blockchains
            if source_chain not in wallet.chains:
                raise ValueError(f"Blockchain source {source_chain.value} non configurée")
            
            if target_chain not in wallet.chains and not recipient_address:
                raise ValueError(f"Blockchain cible {target_chain.value} non configurée")

            # Récupération des wallets
            source_wallet_key = f"{wallet_id}_{source_chain.value}"
            if source_wallet_key not in self._chain_wallets:
                raise ValueError(f"Wallet source non initialisé")

            source_wallet = self._chain_wallets[source_wallet_key]

            # Récupération du bridge
            bridge_config = await self._get_bridge_config(source_chain, target_chain)
            if not bridge_config:
                raise ValueError(f"Bridge non disponible entre {source_chain.value} et {target_chain.value}")

            # Création de la transaction cross-chain
            cross_tx_id = uuid4()
            
            # Transaction source
            source_tx = await source_wallet.send_transaction(
                to_address=bridge_config["bridge_address"],
                amount=amount,
                token_address=token_address,
                metadata={
                    "cross_chain": True,
                    "target_chain": target_chain.value,
                    "cross_tx_id": str(cross_tx_id)
                }
            )

            # Création de l'objet cross-chain
            cross_tx = CrossChainTransaction(
                tx_id=cross_tx_id,
                user_id=wallet.user_id,
                source_chain=source_chain,
                target_chain=target_chain,
                source_tx=source_tx,
                amount=amount,
                amount_usd=source_tx.amount_usd,
                token_address=token_address,
                token_symbol=source_tx.token_symbol,
                status="pending_bridge",
                metadata=metadata or {}
            )

            # Mise en cache
            self._transaction_cache[str(cross_tx_id)] = cross_tx

            # Lancement du monitoring du bridge
            asyncio.create_task(self._monitor_bridge(cross_tx_id))

            logger.info(f"Transaction cross-chain créée: {cross_tx_id}")
            return cross_tx

        except Exception as e:
            logger.error(f"Erreur lors du transfert cross-chain: {e}")
            raise

    async def _get_bridge_config(
        self,
        source_chain: ChainType,
        target_chain: ChainType
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère la configuration d'un bridge.

        Args:
            source_chain: Blockchain source
            target_chain: Blockchain cible

        Returns:
            Configuration du bridge
        """
        bridge_key = f"{source_chain.value}_to_{target_chain.value}"
        return BRIDGE_CONFIG.get(bridge_key)

    async def _monitor_bridge(self, cross_tx_id: UUID) -> None:
        """
        Surveille l'avancement d'une transaction cross-chain.

        Args:
            cross_tx_id: ID de la transaction cross-chain
        """
        try:
            cross_tx = self._transaction_cache.get(str(cross_tx_id))
            if not cross_tx:
                return

            # Monitoring du bridge
            # Pour l'exemple, nous simulons une confirmation
            await asyncio.sleep(30)  # Attente de 30 secondes

            cross_tx.status = "completed"
            cross_tx.completed_at = datetime.now()

            logger.info(f"Transaction cross-chain {cross_tx_id} complétée")

        except Exception as e:
            logger.error(f"Erreur lors du monitoring du bridge: {e}")

    async def get_cross_chain_transaction(
        self,
        tx_id: UUID
    ) -> Optional[CrossChainTransaction]:
        """
        Récupère une transaction cross-chain.

        Args:
            tx_id: ID de la transaction

        Returns:
            Transaction cross-chain
        """
        return self._transaction_cache.get(str(tx_id))

    async def get_cross_chain_transactions(
        self,
        user_id: UUID,
        source_chain: Optional[ChainType] = None,
        target_chain: Optional[ChainType] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[CrossChainTransaction]:
        """
        Récupère les transactions cross-chain d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            source_chain: Filtrer par blockchain source
            target_chain: Filtrer par blockchain cible
            status: Filtrer par statut
            limit: Nombre de transactions
            offset: Décalage

        Returns:
            Liste des transactions cross-chain
        """
        transactions = []
        
        for tx in self._transaction_cache.values():
            if tx.user_id != user_id:
                continue
            
            if source_chain and tx.source_chain != source_chain:
                continue
            
            if target_chain and tx.target_chain != target_chain:
                continue
            
            if status and tx.status != status:
                continue
            
            transactions.append(tx)

        # Tri par date
        transactions.sort(key=lambda x: x.created_at, reverse=True)
        
        return transactions[offset:offset + limit]

    # ========================================================================
    # MÉTHODES D'ANALYTIQUE
    # ========================================================================

    async def get_portfolio_summary(
        self,
        wallet_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère le résumé du portefeuille multi-chain.

        Args:
            wallet_id: ID du wallet

        Returns:
            Résumé du portefeuille
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return {}

            summary = {
                "wallet_id": str(wallet_id),
                "name": wallet.name,
                "primary_chain": wallet.primary_chain.value,
                "total_balance_usd": Decimal("0"),
                "chains": {},
                "tokens": {},
                "total_transactions": 0,
                "total_volume_usd": Decimal("0"),
                "last_updated": datetime.now().isoformat()
            }

            total_balance = Decimal("0")

            for chain_type in wallet.chains.keys():
                chain_key = f"{wallet_id}_{chain_type.value}"
                if chain_key in self._chain_wallets:
                    chain_wallet = self._chain_wallets[chain_key]
                    balance = await chain_wallet.get_balance()
                    
                    chain_balance = {
                        "native": float(balance.native_balance),
                        "native_usd": float(balance.native_balance_usd),
                        "tokens": {k: float(v) for k, v in balance.token_balances.items()},
                        "tokens_usd": {k: float(v) for k, v in balance.token_balances_usd.items()},
                        "total_usd": float(balance.total_balance_usd)
                    }
                    
                    summary["chains"][chain_type.value] = chain_balance
                    total_balance += balance.total_balance_usd

            summary["total_balance_usd"] = float(total_balance)
            
            return summary

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du résumé du portefeuille: {e}")
            return {}

    async def get_chain_statistics(
        self,
        chain: ChainType
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques d'une blockchain.

        Args:
            chain: Blockchain

        Returns:
            Statistiques de la blockchain
        """
        try:
            stats = {
                "chain": chain.value,
                "total_wallets": 0,
                "total_transactions": 0,
                "total_volume_usd": Decimal("0"),
                "active_wallets": 0,
                "average_balance_usd": Decimal("0"),
                "popular_tokens": [],
                "last_updated": datetime.now().isoformat()
            }

            # Comptage des wallets
            for wallet in self._wallet_cache.values():
                if chain in wallet.chains:
                    stats["total_wallets"] += 1
                    if wallet.status == WalletStatus.ACTIVE:
                        stats["active_wallets"] += 1

            return stats

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return {}

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def add_chain_to_wallet(
        self,
        wallet_id: UUID,
        chain: ChainType,
        private_key: Optional[str] = None,
        mnemonic: Optional[str] = None
    ) -> bool:
        """
        Ajoute une blockchain à un wallet existant.

        Args:
            wallet_id: ID du wallet
            chain: Blockchain à ajouter
            private_key: Clé privée (optionnel)
            mnemonic: Phrase mnémonique (optionnel)

        Returns:
            True si l'ajout a réussi
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return False

            if chain in wallet.chains:
                logger.warning(f"Blockchain {chain.value} déjà présente dans le wallet")
                return False

            # Création de la configuration
            chain_name = chain.value
            network = self._get_default_network(chain)
            
            if not private_key and mnemonic:
                private_key = await self._derive_private_key_from_mnemonic(mnemonic, chain)
            elif not private_key:
                private_key = await self._generate_private_key(chain)

            config = WalletConfig(
                wallet_id=wallet_id,
                user_id=wallet.user_id,
                name=f"{wallet.name} - {chain_name.upper()}",
                type=WalletType.HD,
                blockchain=chain_name,
                network=network,
                address="",
                private_key_encrypted=private_key,
                is_created=True,
                is_imported=bool(private_key or mnemonic),
                status=WalletStatus.ACTIVE,
                metadata={"source": "nexus_multi_chain_added"}
            )

            # Initialisation du wallet spécifique
            chain_wallet = await self._init_chain_wallet(chain, config)
            if chain_wallet:
                await chain_wallet.initialize()
                config.address = chain_wallet.config.address
                self._chain_wallets[f"{wallet_id}_{chain.value}"] = chain_wallet
                wallet.chains[chain] = config
                
                logger.info(f"Blockchain {chain.value} ajoutée au wallet {wallet_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la blockchain: {e}")
            return False

    async def remove_chain_from_wallet(
        self,
        wallet_id: UUID,
        chain: ChainType
    ) -> bool:
        """
        Supprime une blockchain d'un wallet.

        Args:
            wallet_id: ID du wallet
            chain: Blockchain à supprimer

        Returns:
            True si la suppression a réussi
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return False

            if chain not in wallet.chains:
                return False

            if chain == wallet.primary_chain:
                logger.warning("Impossible de supprimer la blockchain principale")
                return False

            # Suppression du wallet spécifique
            chain_key = f"{wallet_id}_{chain.value}"
            if chain_key in self._chain_wallets:
                await self._chain_wallets[chain_key].close()
                del self._chain_wallets[chain_key]

            # Suppression de la configuration
            del wallet.chains[chain]
            wallet.updated_at = datetime.now()

            logger.info(f"Blockchain {chain.value} supprimée du wallet {wallet_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la blockchain: {e}")
            return False

    async def set_primary_chain(
        self,
        wallet_id: UUID,
        chain: ChainType
    ) -> bool:
        """
        Définit la blockchain principale d'un wallet.

        Args:
            wallet_id: ID du wallet
            chain: Blockchain à définir comme principale

        Returns:
            True si la mise à jour a réussi
        """
        try:
            wallet = await self.get_wallet(wallet_id)
            if not wallet:
                return False

            if chain not in wallet.chains:
                return False

            wallet.primary_chain = chain
            wallet.updated_at = datetime.now()

            logger.info(f"Blockchain principale du wallet {wallet_id} définie sur {chain.value}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la définition de la blockchain principale: {e}")
            return False

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================

    def _get_default_network(self, chain: ChainType) -> BlockchainNetwork:
        """
        Récupère le réseau par défaut pour une blockchain.

        Args:
            chain: Blockchain

        Returns:
            Réseau par défaut
        """
        default_networks = {
            ChainType.ETHEREUM: BlockchainNetwork.ETHEREUM_MAINNET,
            ChainType.BSC: BlockchainNetwork.BSC_MAINNET,
            ChainType.POLYGON: BlockchainNetwork.POLYGON_MAINNET,
            ChainType.SOLANA: BlockchainNetwork.SOLANA_MAINNET,
            ChainType.AVALANCHE: BlockchainNetwork.AVALANCHE_MAINNET,
            ChainType.ARBITRUM: BlockchainNetwork.ARBITRUM_MAINNET,
            ChainType.OPTIMISM: BlockchainNetwork.OPTIMISM_MAINNET
        }
        return default_networks.get(chain, BlockchainNetwork.ETHEREUM_MAINNET)

    async def _generate_private_key(self, chain: ChainType) -> str:
        """
        Génère une clé privée pour une blockchain.

        Args:
            chain: Blockchain

        Returns:
            Clé privée générée
        """
        try:
            if chain in [ChainType.ETHEREUM, ChainType.BSC, ChainType.POLYGON,
                         ChainType.AVALANCHE, ChainType.ARBITRUM, ChainType.OPTIMISM]:
                account = Account.create()
                return account.key.hex()
            elif chain == ChainType.SOLANA:
                from solders.keypair import Keypair
                keypair = Keypair()
                return base58.b58encode(bytes(keypair)).decode('utf-8')
            else:
                # Fallback sur Ethereum
                account = Account.create()
                return account.key.hex()
        except Exception as e:
            logger.error(f"Erreur lors de la génération de la clé privée: {e}")
            raise

    async def _derive_private_key_from_mnemonic(
        self,
        mnemonic: str,
        chain: ChainType
    ) -> str:
        """
        Dérive une clé privée depuis une phrase mnémonique.

        Args:
            mnemonic: Phrase mnémonique
            chain: Blockchain

        Returns:
            Clé privée dérivée
        """
        try:
            # Pour Ethereum et EVM
            if chain in [ChainType.ETHEREUM, ChainType.BSC, ChainType.POLYGON,
                         ChainType.AVALANCHE, ChainType.ARBITRUM, ChainType.OPTIMISM]:
                Account.enable_unaudited_hdwallet_features()
                account = Account.from_mnemonic(mnemonic)
                return account.key.hex()
            else:
                raise NotImplementedError(f"Dérivation non supportée pour {chain.value}")
        except Exception as e:
            logger.error(f"Erreur lors de la dérivation de la clé privée: {e}")
            raise

    async def get_supported_chains(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des blockchains supportées.

        Returns:
            Liste des blockchains supportées
        """
        chains = []
        for chain in ChainType:
            chains.append({
                "id": chain.value,
                "name": chain.name.capitalize(),
                "networks": [n.value for n in CHAIN_NETWORKS.get(chain, [])],
                "tokens": list(CHAIN_TOKENS.get(chain, {}).keys()),
                "is_evm": chain in [
                    ChainType.ETHEREUM,
                    ChainType.BSC,
                    ChainType.POLYGON,
                    ChainType.AVALANCHE,
                    ChainType.ARBITRUM,
                    ChainType.OPTIMISM
                ]
            })
        return chains

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du gestionnaire multi-chain.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_wallets": self._metrics["total_wallets"],
                "active_wallets": self._metrics["active_wallets"],
                "total_transactions": self._metrics["total_transactions"],
                "total_volume_usd": float(self._metrics["total_volume_usd"]),
                "chains_supported": len(ChainType),
                "cached_wallets": len(self._wallet_cache),
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
        logger.info("Fermeture du MultiChainWalletManager...")
        
        for wallet in self._chain_wallets.values():
            try:
                await wallet.close()
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture du wallet: {e}")
        
        self._wallet_cache.clear()
        self._chain_wallets.clear()
        self._transaction_cache.clear()
        
        logger.info("MultiChainWalletManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_multi_chain_manager(
    api_keys: Optional[Dict[str, str]] = None,
    redis_url: str = "redis://localhost:6379/0"
) -> MultiChainWalletManager:
    """
    Crée une instance du gestionnaire multi-chain.

    Args:
        api_keys: Clés API pour les services externes
        redis_url: URL de connexion Redis

    Returns:
        Instance du gestionnaire
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return MultiChainWalletManager(
        api_keys=api_keys,
        redis_client=redis_client
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ChainType",
    "MultiChainWallet",
    "CrossChainTransaction",
    "MultiChainWalletManager",
    "create_multi_chain_manager",
    "CHAIN_NETWORKS",
    "CHAIN_TOKENS",
    "BRIDGE_CONFIG"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire multi-chain."""
    print("=" * 60)
    print("NEXUS AI TRADING - MULTI-CHAIN WALLET MODULE")
    print("=" * 60)

    # Création du gestionnaire
    manager = create_multi_chain_manager(
        api_keys={
            "etherscan": "YOUR_ETHERSCAN_API_KEY",
            "bscscan": "YOUR_BSCSCAN_API_KEY",
            "polygonscan": "YOUR_POLYGONSCAN_API_KEY"
        }
    )

    # Création d'un wallet multi-chain
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = await manager.create_wallet(
        user_id=user_id,
        name="Main Multi-Chain Wallet",
        chains=[ChainType.ETHEREUM, ChainType.BSC, ChainType.POLYGON],
        primary_chain=ChainType.ETHEREUM,
        metadata={"type": "trading"}
    )

    print(f"\n✅ Wallet multi-chain créé:")
    print(f"   ID: {wallet.wallet_id}")
    print(f"   Nom: {wallet.name}")
    print(f"   Blockchain principale: {wallet.primary_chain.value}")
    print(f"   Blockchains: {[c.value for c in wallet.chains.keys()]}")

    # Récupération des adresses
    for chain, config in wallet.chains.items():
        print(f"   {chain.value.upper()}: {config.address[:8]}...{config.address[-8:]}")

    # Récupération des soldes
    balances = await manager.get_wallet_balance(wallet.wallet_id)
    print(f"\n💰 Soldes:")
    for chain_name, balance in balances.items():
        print(f"   {chain_name.upper()}: {balance.native_balance} (${balance.native_balance_usd:.2f})")

    # Résumé du portefeuille
    summary = await manager.get_portfolio_summary(wallet.wallet_id)
    print(f"\n📊 Résumé du portefeuille:")
    print(f"   Solde total: ${summary.get('total_balance_usd', 0):.2f}")
    print(f"   Blockchains: {list(summary.get('chains', {}).keys())}")

    # Vérification de la santé
    health = await manager.get_health()
    print(f"\n❤️ Santé du gestionnaire:")
    print(f"   Statut: {health['status']}")
    print(f"   Wallets: {health['total_wallets']}")
    print(f"   Transactions: {health['total_transactions']}")

    # Fermeture
    await manager.close()

    print("\n" + "=" * 60)
    print("MultiChainWalletManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import base58
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

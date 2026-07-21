"""
NEXUS AI TRADING SYSTEM - ALCHEMY CLIENT MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module client pour l'API Alchemy.
Support complet des fonctionnalités Alchemy: NFT, Token, Transfers, Webhooks, etc.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from web3 import Web3
from eth_account import Account

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class AlchemyNetwork(Enum):
    """Réseaux supportés par Alchemy."""
    ETH_MAINNET = "eth-mainnet"
    ETH_GOERLI = "eth-goerli"
    ETH_SEPOLIA = "eth-sepolia"
    ETH_HOLESKY = "eth-holesky"
    MATIC_MAINNET = "polygon-mainnet"
    MATIC_MUMBAI = "polygon-mumbai"
    ARB_MAINNET = "arb-mainnet"
    ARB_GOERLI = "arb-goerli"
    OPT_MAINNET = "opt-mainnet"
    OPT_GOERLI = "opt-goerli"
    AVAX_MAINNET = "avax-mainnet"
    AVAX_FUJI = "avax-fuji"


class AlchemyModule(Enum):
    """Modules Alchemy disponibles."""
    NFT = "nft"
    TOKEN = "token"
    TRANSFER = "transfer"
    WEBHOOK = "webhook"
    TRANSACTION = "transaction"
    TRACE = "trace"
    DEBUG = "debug"
    ENS = "ens"


@dataclass
class AlchemyNFT:
    """NFT Alchemy."""
    contract_address: str
    token_id: str
    token_type: str  # ERC721, ERC1155
    title: str
    description: str
    image_url: str
    external_url: Optional[str] = None
    attributes: List[Dict[str, Any]] = field(default_factory=list)
    owner: Optional[str] = None
    minted_at: Optional[datetime] = None
    last_sale: Optional[Dict[str, Any]] = None
    floor_price: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "token_type": self.token_type,
            "title": self.title,
            "description": self.description,
            "image_url": self.image_url,
            "external_url": self.external_url,
            "attributes": self.attributes,
            "owner": self.owner,
            "minted_at": self.minted_at.isoformat() if self.minted_at else None,
            "last_sale": self.last_sale,
            "floor_price": str(self.floor_price) if self.floor_price else None,
            "metadata": self.metadata
        }


@dataclass
class AlchemyToken:
    """Token Alchemy (ERC20)."""
    address: str
    symbol: str
    name: str
    decimals: int
    total_supply: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    holders_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            "total_supply": str(self.total_supply) if self.total_supply else None,
            "price_usd": str(self.price_usd) if self.price_usd else None,
            "market_cap": str(self.market_cap) if self.market_cap else None,
            "volume_24h": str(self.volume_24h) if self.volume_24h else None,
            "holders_count": self.holders_count,
            "metadata": self.metadata
        }


@dataclass
class AlchemyTransfer:
    """Transfert Alchemy."""
    hash: str
    from_address: str
    to_address: str
    value: Decimal
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    token_decimals: Optional[int] = None
    block_number: int = 0
    block_timestamp: datetime = field(default_factory=datetime.now)
    gas_price: Optional[Decimal] = None
    gas_used: Optional[int] = None
    tx_fee: Optional[Decimal] = None
    status: str = "confirmed"  # pending, confirmed, failed
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "hash": self.hash,
            "from": self.from_address,
            "to": self.to_address,
            "value": str(self.value),
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "token_decimals": self.token_decimals,
            "block_number": self.block_number,
            "block_timestamp": self.block_timestamp.isoformat(),
            "gas_price": str(self.gas_price) if self.gas_price else None,
            "gas_used": self.gas_used,
            "tx_fee": str(self.tx_fee) if self.tx_fee else None,
            "status": self.status,
            "metadata": self.metadata
        }


@dataclass
class AlchemyWebhook:
    """Webhook Alchemy."""
    id: str
    network: AlchemyNetwork
    webhook_type: str  # ADDRESS_ACTIVITY, NFT_ACTIVITY, MINED_TRANSACTION
    url: str
    addresses: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "network": self.network.value,
            "webhook_type": self.webhook_type,
            "url": self.url,
            "addresses": self.addresses,
            "filters": self.filters,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE ALCHEMY CLIENT
# ============================================================================

class AlchemyClient:
    """
    Client pour l'API Alchemy.
    Support des NFT, Tokens, Transfers, Webhooks, etc.
    """

    # URLs par réseau
    BASE_URLS = {
        AlchemyNetwork.ETH_MAINNET: "https://eth-mainnet.g.alchemy.com",
        AlchemyNetwork.ETH_GOERLI: "https://eth-goerli.g.alchemy.com",
        AlchemyNetwork.ETH_SEPOLIA: "https://eth-sepolia.g.alchemy.com",
        AlchemyNetwork.ETH_HOLESKY: "https://eth-holesky.g.alchemy.com",
        AlchemyNetwork.MATIC_MAINNET: "https://polygon-mainnet.g.alchemy.com",
        AlchemyNetwork.MATIC_MUMBAI: "https://polygon-mumbai.g.alchemy.com",
        AlchemyNetwork.ARB_MAINNET: "https://arb-mainnet.g.alchemy.com",
        AlchemyNetwork.ARB_GOERLI: "https://arb-goerli.g.alchemy.com",
        AlchemyNetwork.OPT_MAINNET: "https://opt-mainnet.g.alchemy.com",
        AlchemyNetwork.OPT_GOERLI: "https://opt-goerli.g.alchemy.com",
        AlchemyNetwork.AVAX_MAINNET: "https://avax-mainnet.g.alchemy.com",
        AlchemyNetwork.AVAX_FUJI: "https://avax-fuji.g.alchemy.com"
    }

    # NFT API endpoints
    NFT_ENDPOINTS = {
        "get_nft_metadata": "/v2/{api_key}/getNFTMetadata",
        "get_nft_metadata_batch": "/v2/{api_key}/getNFTMetadataBatch",
        "get_nft_owners": "/v2/{api_key}/getNFTs",
        "get_contract_metadata": "/v2/{api_key}/getContractMetadata",
        "get_nft_collections": "/v2/{api_key}/getNFTCollections",
        "get_nft_sales": "/v2/{api_key}/getNFTSales",
        "get_nft_floor_price": "/v2/{api_key}/getNFTFloorPrice",
        "get_nft_rarity": "/v2/{api_key}/getNFTRarity"
    }

    # Token API endpoints
    TOKEN_ENDPOINTS = {
        "get_token_metadata": "/v2/{api_key}/getTokenMetadata",
        "get_token_balances": "/v2/{api_key}/getTokenBalances",
        "get_token_holders": "/v2/{api_key}/getTokenHolders",
        "get_token_price": "/v2/{api_key}/getTokenPrice"
    }

    # Transfer API endpoints
    TRANSFER_ENDPOINTS = {
        "get_transfers": "/v2/{api_key}/getTransfers",
        "get_historical_transfers": "/v2/{api_key}/getHistoricalTransfers"
    }

    # Webhook API endpoints
    WEBHOOK_ENDPOINTS = {
        "create_webhook": "/v2/{api_key}/createWebhook",
        "list_webhooks": "/v2/{api_key}/listWebhooks",
        "delete_webhook": "/v2/{api_key}/deleteWebhook",
        "update_webhook": "/v2/{api_key}/updateWebhook",
        "get_webhook": "/v2/{api_key}/getWebhook"
    }

    def __init__(
        self,
        api_key: str,
        network: AlchemyNetwork = AlchemyNetwork.ETH_MAINNET,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le client Alchemy.

        Args:
            api_key: Clé API Alchemy
            network: Réseau cible
            api_keys: Clés API supplémentaires
        """
        self.api_key = api_key
        self.network = network
        self.api_keys = api_keys or {}
        
        # Base URL
        self.base_url = self.BASE_URLS.get(network)
        if not self.base_url:
            raise ValueError(f"Réseau non supporté: {network}")

        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cache
        self._nft_cache: Dict[str, AlchemyNFT] = {}
        self._token_cache: Dict[str, AlchemyToken] = {}
        self._transfer_cache: Dict[str, AlchemyTransfer] = {}
        
        # Métriques
        self._metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "by_endpoint": {},
            "last_request": None
        }

        logger.info(f"AlchemyClient initialisé pour {network.value}")

    async def __aenter__(self):
        """Context manager enter."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Assure qu'une session HTTP est disponible."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Effectue une requête vers l'API Alchemy.

        Args:
            endpoint: Point d'accès
            params: Paramètres
            data: Données POST
            method: Méthode HTTP

        Returns:
            Réponse JSON
        """
        try:
            await self._ensure_session()
            
            # Construction de l'URL
            url = f"{self.base_url}{endpoint.format(api_key=self.api_key)}"
            
            # En-têtes
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            # Métriques
            endpoint_name = endpoint.split("/")[-1]
            self._metrics["total_requests"] += 1
            self._metrics["last_request"] = datetime.now().isoformat()
            
            if endpoint_name not in self._metrics["by_endpoint"]:
                self._metrics["by_endpoint"][endpoint_name] = 0
            self._metrics["by_endpoint"][endpoint_name] += 1

            # Requête
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    self._metrics["total_errors"] += 1
                    raise Exception(f"Erreur Alchemy ({response.status}): {error_text}")

        except Exception as e:
            logger.error(f"Erreur lors de la requête Alchemy: {e}")
            self._metrics["total_errors"] += 1
            raise

    # ========================================================================
    # API NFT
    # ========================================================================

    async def get_nft_metadata(
        self,
        contract_address: str,
        token_id: str,
        include_metadata: bool = True
    ) -> Optional[AlchemyNFT]:
        """
        Récupère les métadonnées d'un NFT.

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            include_metadata: Inclure les métadonnées

        Returns:
            NFT Alchemy
        """
        try:
            cache_key = f"{contract_address}:{token_id}"
            if cache_key in self._nft_cache:
                return self._nft_cache[cache_key]

            params = {
                "contractAddress": contract_address,
                "tokenId": token_id,
                "refreshCache": str(not include_metadata).lower()
            }

            data = await self._request(
                self.NFT_ENDPOINTS["get_nft_metadata"],
                params=params
            )

            if data and data.get("contract"):
                nft = self._parse_nft_response(data)
                self._nft_cache[cache_key] = nft
                return nft

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métadonnées NFT: {e}")
            return None

    async def get_nft_owners(
        self,
        contract_address: str,
        token_ids: Optional[List[str]] = None,
        page_size: int = 100,
        page_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Récupère les propriétaires de NFTs.

        Args:
            contract_address: Adresse du contrat
            token_ids: IDs des tokens (optionnel)
            page_size: Taille de page
            page_key: Clé de page

        Returns:
            Résultats des propriétaires
        """
        try:
            params = {
                "contractAddress": contract_address,
                "withMetadata": "true"
            }

            if token_ids:
                params["tokenIds"] = ",".join(token_ids)
            if page_size:
                params["pageSize"] = page_size
            if page_key:
                params["pageKey"] = page_key

            return await self._request(
                self.NFT_ENDPOINTS["get_nft_owners"],
                params=params
            )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des propriétaires NFT: {e}")
            return {}

    async def get_contract_metadata(
        self,
        contract_address: str
    ) -> Dict[str, Any]:
        """
        Récupère les métadonnées d'un contrat NFT.

        Args:
            contract_address: Adresse du contrat

        Returns:
            Métadonnées du contrat
        """
        try:
            params = {"contractAddress": contract_address}

            return await self._request(
                self.NFT_ENDPOINTS["get_contract_metadata"],
                params=params
            )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métadonnées du contrat: {e}")
            return {}

    async def get_nft_collections(
        self,
        address: str,
        page_size: int = 100,
        page_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Récupère les collections NFT d'une adresse.

        Args:
            address: Adresse du wallet
            page_size: Taille de page
            page_key: Clé de page

        Returns:
            Collections NFT
        """
        try:
            params = {
                "owner": address,
                "pageSize": page_size
            }

            if page_key:
                params["pageKey"] = page_key

            return await self._request(
                self.NFT_ENDPOINTS["get_nft_collections"],
                params=params
            )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des collections NFT: {e}")
            return {}

    async def get_nft_floor_price(
        self,
        contract_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère le floor price d'une collection NFT.

        Args:
            contract_address: Adresse du contrat

        Returns:
            Floor price
        """
        try:
            params = {"contractAddress": contract_address}

            return await self._request(
                self.NFT_ENDPOINTS["get_nft_floor_price"],
                params=params
            )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du floor price: {e}")
            return None

    # ========================================================================
    # API TOKENS
    # ========================================================================

    async def get_token_metadata(
        self,
        contract_address: str
    ) -> Optional[AlchemyToken]:
        """
        Récupère les métadonnées d'un token.

        Args:
            contract_address: Adresse du contrat

        Returns:
            Token Alchemy
        """
        try:
            if contract_address in self._token_cache:
                return self._token_cache[contract_address]

            params = {"contractAddress": contract_address}

            data = await self._request(
                self.TOKEN_ENDPOINTS["get_token_metadata"],
                params=params
            )

            if data:
                token = self._parse_token_response(data)
                self._token_cache[contract_address] = token
                return token

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métadonnées du token: {e}")
            return None

    async def get_token_balances(
        self,
        address: str,
        contract_addresses: Optional[List[str]] = None
    ) -> Dict[str, Decimal]:
        """
        Récupère les soldes de tokens.

        Args:
            address: Adresse du wallet
            contract_addresses: Adresses des contrats

        Returns:
            Soldes des tokens
        """
        try:
            params = {"address": address}

            if contract_addresses:
                params["contractAddresses"] = ",".join(contract_addresses)

            data = await self._request(
                self.TOKEN_ENDPOINTS["get_token_balances"],
                params=params
            )

            balances = {}
            if data and data.get("tokenBalances"):
                for token in data["tokenBalances"]:
                    token_address = token.get("contractAddress")
                    balance = Decimal(str(token.get("tokenBalance", 0))) / Decimal(str(10 ** token.get("decimals", 18)))
                    balances[token_address] = balance

            return balances

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des soldes de tokens: {e}")
            return {}

    async def get_token_price(
        self,
        contract_address: str
    ) -> Optional[Decimal]:
        """
        Récupère le prix d'un token.

        Args:
            contract_address: Adresse du contrat

        Returns:
            Prix du token
        """
        try:
            params = {"contractAddress": contract_address}

            data = await self._request(
                self.TOKEN_ENDPOINTS["get_token_price"],
                params=params
            )

            if data:
                price = data.get("price")
                return Decimal(str(price)) if price else None

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix du token: {e}")
            return None

    # ========================================================================
    # API TRANSFERS
    # ========================================================================

    async def get_transfers(
        self,
        address: str,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        token_address: Optional[str] = None,
        category: Optional[List[str]] = None,
        page_size: int = 100,
        page_key: Optional[str] = None
    ) -> List[AlchemyTransfer]:
        """
        Récupère les transferts d'une adresse.

        Args:
            address: Adresse du wallet
            from_block: Bloc de début
            to_block: Bloc de fin
            token_address: Adresse du token
            category: Catégories de transferts
            page_size: Taille de page
            page_key: Clé de page

        Returns:
            Liste des transferts
        """
        try:
            params = {"address": address}

            if from_block:
                params["fromBlock"] = str(from_block)
            if to_block:
                params["toBlock"] = str(to_block)
            if token_address:
                params["contractAddress"] = token_address
            if category:
                params["category"] = ",".join(category)
            if page_size:
                params["pageSize"] = page_size
            if page_key:
                params["pageKey"] = page_key

            data = await self._request(
                self.TRANSFER_ENDPOINTS["get_transfers"],
                params=params
            )

            transfers = []
            if data and data.get("transfers"):
                for tx in data["transfers"]:
                    transfer = self._parse_transfer_response(tx)
                    transfers.append(transfer)

            return transfers

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des transferts: {e}")
            return []

    async def get_historical_transfers(
        self,
        address: str,
        token_address: str,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        page_size: int = 100,
        page_key: Optional[str] = None
    ) -> List[AlchemyTransfer]:
        """
        Récupère les transferts historiques.

        Args:
            address: Adresse du wallet
            token_address: Adresse du token
            from_block: Bloc de début
            to_block: Bloc de fin
            page_size: Taille de page
            page_key: Clé de page

        Returns:
            Liste des transferts historiques
        """
        try:
            params = {
                "address": address,
                "contractAddress": token_address
            }

            if from_block:
                params["fromBlock"] = str(from_block)
            if to_block:
                params["toBlock"] = str(to_block)
            if page_size:
                params["pageSize"] = page_size
            if page_key:
                params["pageKey"] = page_key

            data = await self._request(
                self.TRANSFER_ENDPOINTS["get_historical_transfers"],
                params=params
            )

            transfers = []
            if data and data.get("transfers"):
                for tx in data["transfers"]:
                    transfer = self._parse_transfer_response(tx)
                    transfers.append(transfer)

            return transfers

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des transferts historiques: {e}")
            return []

    # ========================================================================
    # API WEBHOOKS
    # ========================================================================

    async def create_webhook(
        self,
        webhook_type: str,
        url: str,
        addresses: List[str],
        network: Optional[AlchemyNetwork] = None,
        filters: Optional[Dict] = None
    ) -> Optional[AlchemyWebhook]:
        """
        Crée un webhook Alchemy.

        Args:
            webhook_type: Type de webhook
            url: URL de destination
            addresses: Adresses à surveiller
            network: Réseau (optionnel)
            filters: Filtres (optionnel)

        Returns:
            Webhook Alchemy
        """
        try:
            data = {
                "webhook_type": webhook_type,
                "webhook_url": url,
                "addresses": addresses,
                "network": (network or self.network).value
            }

            if filters:
                data["filters"] = filters

            result = await self._request(
                self.WEBHOOK_ENDPOINTS["create_webhook"],
                data=data,
                method="POST"
            )

            if result and result.get("data"):
                return self._parse_webhook_response(result["data"])

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la création du webhook: {e}")
            return None

    async def list_webhooks(
        self,
        active_only: bool = True
    ) -> List[AlchemyWebhook]:
        """
        Liste les webhooks.

        Args:
            active_only: Uniquement les webhooks actifs

        Returns:
            Liste des webhooks
        """
        try:
            data = await self._request(
                self.WEBHOOK_ENDPOINTS["list_webhooks"]
            )

            webhooks = []
            if data and data.get("data"):
                for wh in data["data"]:
                    webhook = self._parse_webhook_response(wh)
                    if active_only and not webhook.active:
                        continue
                    webhooks.append(webhook)

            return webhooks

        except Exception as e:
            logger.error(f"Erreur lors de la liste des webhooks: {e}")
            return []

    async def delete_webhook(
        self,
        webhook_id: str
    ) -> bool:
        """
        Supprime un webhook.

        Args:
            webhook_id: ID du webhook

        Returns:
            True si la suppression a réussi
        """
        try:
            await self._request(
                self.WEBHOOK_ENDPOINTS["delete_webhook"],
                params={"webhookId": webhook_id},
                method="DELETE"
            )
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du webhook: {e}")
            return False

    async def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        active: Optional[bool] = None,
        filters: Optional[Dict] = None
    ) -> Optional[AlchemyWebhook]:
        """
        Met à jour un webhook.

        Args:
            webhook_id: ID du webhook
            url: Nouvelle URL
            active: Nouveau statut actif
            filters: Nouveaux filtres

        Returns:
            Webhook mis à jour
        """
        try:
            data = {"webhookId": webhook_id}

            if url:
                data["webhook_url"] = url
            if active is not None:
                data["is_active"] = active
            if filters:
                data["filters"] = filters

            result = await self._request(
                self.WEBHOOK_ENDPOINTS["update_webhook"],
                data=data,
                method="PUT"
            )

            if result and result.get("data"):
                return self._parse_webhook_response(result["data"])

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du webhook: {e}")
            return None

    # ========================================================================
    # MÉTHODES DE PARSING
    # ========================================================================

    def _parse_nft_response(self, data: Dict) -> AlchemyNFT:
        """
        Parse une réponse NFT.

        Args:
            data: Données brutes

        Returns:
            NFT Alchemy
        """
        contract = data.get("contract", {})
        metadata = data.get("metadata", {})
        time_last_updated = data.get("timeLastUpdated")

        return AlchemyNFT(
            contract_address=contract.get("address", ""),
            token_id=data.get("tokenId", ""),
            token_type=contract.get("tokenType", "ERC721"),
            title=metadata.get("name", ""),
            description=metadata.get("description", ""),
            image_url=metadata.get("image", ""),
            external_url=metadata.get("external_url"),
            attributes=metadata.get("attributes", []),
            owner=metadata.get("owner_of"),
            minted_at=datetime.fromisoformat(time_last_updated) if time_last_updated else None,
            metadata=metadata
        )

    def _parse_token_response(self, data: Dict) -> AlchemyToken:
        """
        Parse une réponse token.

        Args:
            data: Données brutes

        Returns:
            Token Alchemy
        """
        return AlchemyToken(
            address=data.get("address", ""),
            symbol=data.get("symbol", ""),
            name=data.get("name", ""),
            decimals=data.get("decimals", 18),
            total_supply=Decimal(str(data.get("totalSupply", 0))),
            metadata=data
        )

    def _parse_transfer_response(self, data: Dict) -> AlchemyTransfer:
        """
        Parse une réponse transfert.

        Args:
            data: Données brutes

        Returns:
            Transfert Alchemy
        """
        return AlchemyTransfer(
            hash=data.get("hash", ""),
            from_address=data.get("from", ""),
            to_address=data.get("to", ""),
            value=Decimal(str(data.get("value", 0))),
            token_address=data.get("contractAddress"),
            token_symbol=data.get("symbol"),
            token_decimals=data.get("decimals"),
            block_number=data.get("blockNum", 0),
            block_timestamp=datetime.fromtimestamp(data.get("timestamp", 0)) if data.get("timestamp") else datetime.now(),
            gas_price=Decimal(str(data.get("gasPrice", 0))) if data.get("gasPrice") else None,
            gas_used=data.get("gasUsed"),
            status=data.get("status", "confirmed"),
            metadata=data
        )

    def _parse_webhook_response(self, data: Dict) -> AlchemyWebhook:
        """
        Parse une réponse webhook.

        Args:
            data: Données brutes

        Returns:
            Webhook Alchemy
        """
        return AlchemyWebhook(
            id=data.get("id", ""),
            network=AlchemyNetwork(data.get("network", "eth-mainnet")),
            webhook_type=data.get("webhook_type", ""),
            url=data.get("webhook_url", ""),
            addresses=data.get("addresses", []),
            filters=data.get("filters", {}),
            active=data.get("is_active", True),
            created_at=datetime.fromtimestamp(data.get("created_at", 0)) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromtimestamp(data.get("updated_at", 0)) if data.get("updated_at") else datetime.now(),
            metadata=data
        )

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du client.

        Returns:
            État de santé
        """
        try:
            # Test de la connexion
            await self.get_token_price("0xdAC17F958D2ee523a2206206994597C13D831ec7")  # USDT
            connected = True
        except Exception:
            connected = False

        return {
            "status": "healthy" if connected else "unhealthy",
            "network": self.network.value,
            "api_key": self.api_key[:8] + "..." if self.api_key else "N/A",
            "total_requests": self._metrics["total_requests"],
            "total_errors": self._metrics["total_errors"],
            "by_endpoint": self._metrics["by_endpoint"],
            "last_request": self._metrics["last_request"],
            "cached_nfts": len(self._nft_cache),
            "cached_tokens": len(self._token_cache),
            "cached_transfers": len(self._transfer_cache),
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_alchemy_client(
    api_key: str,
    network: AlchemyNetwork = AlchemyNetwork.ETH_MAINNET,
    api_keys: Optional[Dict[str, str]] = None
) -> AlchemyClient:
    """
    Crée une instance du client Alchemy.

    Args:
        api_key: Clé API Alchemy
        network: Réseau cible
        api_keys: Clés API supplémentaires

    Returns:
        Client Alchemy
    """
    return AlchemyClient(
        api_key=api_key,
        network=network,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AlchemyNetwork",
    "AlchemyModule",
    "AlchemyNFT",
    "AlchemyToken",
    "AlchemyTransfer",
    "AlchemyWebhook",
    "AlchemyClient",
    "create_alchemy_client"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du client Alchemy."""
    print("=" * 60)
    print("NEXUS AI TRADING - ALCHEMY CLIENT MODULE")
    print("=" * 60)

    # Création du client
    client = create_alchemy_client(
        api_key="YOUR_ALCHEMY_API_KEY",
        network=AlchemyNetwork.ETH_MAINNET
    )

    print(f"\n✅ Client Alchemy initialisé:")
    print(f"   Réseau: {client.network.value}")
    print(f"   Base URL: {client.base_url}")

    # Récupération des métadonnées d'un NFT
    print(f"\n🎨 Récupération des métadonnées NFT...")
    nft = await client.get_nft_metadata(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1"
    )
    if nft:
        print(f"   Titre: {nft.title}")
        print(f"   Description: {nft.description[:50]}...")
        print(f"   Image: {nft.image_url[:50]}...")

    # Récupération du prix d'un token
    print(f"\n💰 Récupération du prix USDT...")
    price = await client.get_token_price("0xdAC17F958D2ee523a2206206994597C13D831ec7")
    if price:
        print(f"   Prix USDT: ${price:.4f}")

    # Récupération des transferts
    print(f"\n📊 Récupération des transferts...")
    transfers = await client.get_transfers(
        address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        category=["external", "token"],
        page_size=5
    )
    print(f"   {len(transfers)} transferts récupérés")

    # Santé du client
    health = await client.get_health()
    print(f"\n❤️ Santé du client:")
    print(f"   Statut: {health['status']}")
    print(f"   Requêtes: {health['total_requests']}")
    print(f"   Erreurs: {health['total_errors']}")

    # Fermeture
    await client.close()

    print("\n" + "=" * 60)
    print("AlchemyClient NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

"""
NEXUS AI TRADING SYSTEM - WALLET BALANCE MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des soldes pour wallets multi-blockchain.
Support des balances natives, tokens, NFT, et métriques avancées.

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

class BalanceType(Enum):
    """Types de solde."""
    NATIVE = "native"
    TOKEN = "token"
    NFT = "nft"
    STAKED = "staked"
    LOCKED = "locked"
    PENDING = "pending"
    AVAILABLE = "available"
    TOTAL = "total"


class PriceSource(Enum):
    """Sources de prix."""
    COINGECKO = "coingecko"
    COINMARKETCAP = "coinmarketcap"
    DEFI_PULSE = "defi_pulse"
    BINANCE = "binance"
    UNISWAP = "uniswap"
    PANCAKESWAP = "pancakeswap"
    QUICKSWAP = "quickswap"
    ORCA = "orca"


@dataclass
class TokenPrice:
    """Prix d'un token."""
    symbol: str
    price_usd: Decimal
    price_btc: Decimal
    price_eth: Decimal
    volume_24h: Decimal
    market_cap: Decimal
    liquidity: Decimal
    source: PriceSource
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "symbol": self.symbol,
            "price_usd": str(self.price_usd),
            "price_btc": str(self.price_btc),
            "price_eth": str(self.price_eth),
            "volume_24h": str(self.volume_24h),
            "market_cap": str(self.market_cap),
            "liquidity": str(self.liquidity),
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class BalanceSnapshot:
    """Snapshot de solde."""
    wallet_id: UUID
    timestamp: datetime
    native_balance: Decimal
    native_balance_usd: Decimal
    token_balances: Dict[str, Decimal]
    token_balances_usd: Dict[str, Decimal]
    nft_balances: Dict[str, int]
    staked_balances: Dict[str, Decimal]
    locked_balances: Dict[str, Decimal]
    total_balance_usd: Decimal
    price_changes: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "timestamp": self.timestamp.isoformat(),
            "native_balance": str(self.native_balance),
            "native_balance_usd": str(self.native_balance_usd),
            "token_balances": {k: str(v) for k, v in self.token_balances.items()},
            "token_balances_usd": {k: str(v) for k, v in self.token_balances_usd.items()},
            "nft_balances": self.nft_balances,
            "staked_balances": {k: str(v) for k, v in self.staked_balances.items()},
            "locked_balances": {k: str(v) for k, v in self.locked_balances.items()},
            "total_balance_usd": str(self.total_balance_usd),
            "price_changes": self.price_changes,
            "metadata": self.metadata
        }


@dataclass
class BalanceAlert:
    """Alerte de solde."""
    alert_id: UUID
    wallet_id: UUID
    user_id: UUID
    type: str  # "threshold", "change", "price"
    condition: str
    current_value: Decimal
    threshold_value: Decimal
    severity: str  # "info", "warning", "critical"
    message: str
    timestamp: datetime
    acknowledged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "alert_id": str(self.alert_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "type": self.type,
            "condition": self.condition,
            "current_value": str(self.current_value),
            "threshold_value": str(self.threshold_value),
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET BALANCE SERVICE
# ============================================================================

class WalletBalanceService:
    """
    Service de gestion des soldes pour wallets multi-blockchain.
    """

    # URLs des APIs de prix
    PRICE_APIS = {
        PriceSource.COINGECKO: "https://api.coingecko.com/api/v3",
        PriceSource.COINMARKETCAP: "https://pro-api.coinmarketcap.com/v1",
        PriceSource.BINANCE: "https://api.binance.com/api/v3",
        PriceSource.DEFI_PULSE: "https://api.defipulse.com/v1"
    }

    # DEX APIs
    DEX_APIS = {
        "uniswap": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
        "pancakeswap": "https://api.thegraph.com/subgraphs/name/pancakeswap/pancake-v2",
        "quickswap": "https://api.thegraph.com/subgraphs/name/sameepsi/quickswap",
        "orca": "https://api.thegraph.com/subgraphs/name/orca/orca"
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de gestion des soldes.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Cache
        self._balance_cache: Dict[UUID, WalletBalance] = {}
        self._price_cache: Dict[str, TokenPrice] = {}
        self._snapshot_cache: Dict[UUID, List[BalanceSnapshot]] = {}
        self._alert_cache: Dict[UUID, List[BalanceAlert]] = {}
        
        # Alertes configurées
        self._alert_configs: Dict[UUID, List[Dict]] = {}
        
        # Métriques
        self._metrics = {
            "total_balances_checked": 0,
            "total_alerts_triggered": 0,
            "total_price_updates": 0,
            "last_check": None,
            "last_price_update": None
        }

        logger.info("WalletBalanceService initialisé avec succès")

    # ========================================================================
    # GESTION DES SOLDE
    # ========================================================================

    async def get_balance(
        self,
        wallet: BaseWallet,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde d'un wallet.

        Args:
            wallet: Wallet
            token_address: Adresse du token (optionnel)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        try:
            wallet_id = wallet.config.wallet_id
            
            # Vérification du cache
            if not force_refresh and wallet_id in self._balance_cache:
                cached = self._balance_cache[wallet_id]
                if (datetime.now() - cached.last_updated).seconds < 60:
                    return cached

            # Récupération du solde
            balance = await wallet.get_balance(
                token_address=token_address,
                force_refresh=force_refresh
            )

            # Mise en cache
            self._balance_cache[wallet_id] = balance
            
            # Mise à jour des métriques
            self._metrics["total_balances_checked"] += 1
            self._metrics["last_check"] = datetime.now().isoformat()

            return balance

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde: {e}")
            raise

    async def get_balances(
        self,
        wallet: BaseWallet,
        token_addresses: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, WalletBalance]:
        """
        Récupère les soldes de plusieurs tokens.

        Args:
            wallet: Wallet
            token_addresses: Liste des adresses de tokens
            force_refresh: Forcer le rafraîchissement

        Returns:
            Dictionnaire des soldes par adresse
        """
        try:
            wallet_id = wallet.config.wallet_id
            
            # Vérification du cache
            if not force_refresh and wallet_id in self._balance_cache:
                cached = self._balance_cache[wallet_id]
                if (datetime.now() - cached.last_updated).seconds < 60:
                    return {wallet.config.address: cached}

            # Récupération des soldes
            balances = await wallet.get_balances(
                token_addresses=token_addresses,
                force_refresh=force_refresh
            )

            # Mise en cache
            for address, balance in balances.items():
                self._balance_cache[UUID(balance.wallet_id)] = balance

            return balances

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des soldes: {e}")
            raise

    async def get_total_balance(
        self,
        wallet: BaseWallet,
        include_tokens: bool = True,
        include_nfts: bool = False
    ) -> Dict[str, Any]:
        """
        Récupère le solde total d'un wallet.

        Args:
            wallet: Wallet
            include_tokens: Inclure les tokens
            include_nfts: Inclure les NFTs

        Returns:
            Solde total
        """
        try:
            balance = await self.get_balance(wallet, force_refresh=True)
            
            total_usd = balance.total_balance_usd
            
            result = {
                "wallet_id": str(wallet.config.wallet_id),
                "address": wallet.config.address,
                "blockchain": wallet.config.blockchain,
                "network": wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
                "native": {
                    "balance": float(balance.native_balance),
                    "usd": float(balance.native_balance_usd)
                },
                "tokens": {},
                "total_usd": float(total_usd),
                "timestamp": datetime.now().isoformat()
            }

            if include_tokens:
                result["tokens"] = {
                    addr: {
                        "balance": float(bal),
                        "usd": float(balance.token_balances_usd.get(addr, Decimal("0")))
                    }
                    for addr, bal in balance.token_balances.items()
                }

            if include_nfts:
                # Récupération des NFTs
                nfts = await self._get_nft_balances(wallet)
                result["nfts"] = nfts

            return result

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde total: {e}")
            return {}

    # ========================================================================
    # GESTION DES PRIX
    # ========================================================================

    async def get_token_price(
        self,
        symbol: str,
        source: PriceSource = PriceSource.COINGECKO,
        force_refresh: bool = False
    ) -> Optional[TokenPrice]:
        """
        Récupère le prix d'un token.

        Args:
            symbol: Symbole du token
            source: Source de prix
            force_refresh: Forcer le rafraîchissement

        Returns:
            Prix du token
        """
        try:
            cache_key = f"{symbol}_{source.value}"
            
            # Vérification du cache
            if not force_refresh and cache_key in self._price_cache:
                cached = self._price_cache[cache_key]
                if (datetime.now() - cached.timestamp).seconds < 60:
                    return cached

            # Récupération du prix
            if source == PriceSource.COINGECKO:
                price = await self._get_price_coingecko(symbol)
            elif source == PriceSource.COINMARKETCAP:
                price = await self._get_price_coinmarketcap(symbol)
            elif source == PriceSource.BINANCE:
                price = await self._get_price_binance(symbol)
            elif source == PriceSource.DEFI_PULSE:
                price = await self._get_price_defi_pulse(symbol)
            else:
                raise ValueError(f"Source non supportée: {source}")

            if price:
                self._price_cache[cache_key] = price
                self._metrics["total_price_updates"] += 1
                self._metrics["last_price_update"] = datetime.now().isoformat()
                return price

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix pour {symbol}: {e}")
            return None

    async def _get_price_coingecko(self, symbol: str) -> Optional[TokenPrice]:
        """
        Récupère le prix depuis CoinGecko.

        Args:
            symbol: Symbole du token

        Returns:
            Prix du token
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Mapping des symboles
                symbol_map = {
                    "eth": "ethereum",
                    "btc": "bitcoin",
                    "bnb": "binancecoin",
                    "sol": "solana",
                    "matic": "polygon",
                    "avax": "avalanche-2",
                    "trx": "tron",
                    "dot": "polkadot",
                    "ada": "cardano",
                    "usdt": "tether",
                    "usdc": "usd-coin",
                    "dai": "dai",
                    "wbtc": "wrapped-bitcoin",
                    "link": "chainlink",
                    "uni": "uniswap",
                    "aave": "aave",
                    "crv": "curve-dao-token",
                    "mkr": "maker",
                    "comp": "compound"
                }
                
                coin_id = symbol_map.get(symbol.lower(), symbol.lower())
                
                async with session.get(
                    f"{self.PRICE_APIS[PriceSource.COINGECKO]}/simple/price",
                    params={
                        "ids": coin_id,
                        "vs_currencies": "usd,btc,eth",
                        "include_24hr_vol": "true",
                        "include_market_cap": "true"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        coin_data = data.get(coin_id, {})
                        
                        return TokenPrice(
                            symbol=symbol.upper(),
                            price_usd=Decimal(str(coin_data.get("usd", 0))),
                            price_btc=Decimal(str(coin_data.get("btc", 0))),
                            price_eth=Decimal(str(coin_data.get("eth", 0))),
                            volume_24h=Decimal(str(coin_data.get("usd_24h_vol", 0))),
                            market_cap=Decimal(str(coin_data.get("usd_market_cap", 0))),
                            liquidity=Decimal("0"),
                            source=PriceSource.COINGECKO,
                            timestamp=datetime.now()
                        )
            
            return None

        except Exception as e:
            logger.error(f"Erreur CoinGecko pour {symbol}: {e}")
            return None

    async def _get_price_coinmarketcap(self, symbol: str) -> Optional[TokenPrice]:
        """
        Récupère le prix depuis CoinMarketCap.

        Args:
            symbol: Symbole du token

        Returns:
            Prix du token
        """
        try:
            api_key = self.api_keys.get("coinmarketcap")
            if not api_key:
                logger.warning("Clé API CoinMarketCap manquante")
                return None

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.PRICE_APIS[PriceSource.COINMARKETCAP]}/cryptocurrency/quotes/latest",
                    headers={"X-CMC_PRO_API_KEY": api_key},
                    params={"symbol": symbol.upper()}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        quote = data.get("data", {}).get(symbol.upper(), {}).get("quote", {}).get("USD", {})
                        
                        return TokenPrice(
                            symbol=symbol.upper(),
                            price_usd=Decimal(str(quote.get("price", 0))),
                            price_btc=Decimal("0"),
                            price_eth=Decimal("0"),
                            volume_24h=Decimal(str(quote.get("volume_24h", 0))),
                            market_cap=Decimal(str(quote.get("market_cap", 0))),
                            liquidity=Decimal("0"),
                            source=PriceSource.COINMARKETCAP,
                            timestamp=datetime.now()
                        )
            
            return None

        except Exception as e:
            logger.error(f"Erreur CoinMarketCap pour {symbol}: {e}")
            return None

    async def _get_price_binance(self, symbol: str) -> Optional[TokenPrice]:
        """
        Récupère le prix depuis Binance.

        Args:
            symbol: Symbole du token

        Returns:
            Prix du token
        """
        try:
            async with aiohttp.ClientSession() as session:
                pair = f"{symbol.upper()}USDT"
                async with session.get(
                    f"{self.PRICE_APIS[PriceSource.BINANCE]}/ticker/24hr",
                    params={"symbol": pair}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return TokenPrice(
                            symbol=symbol.upper(),
                            price_usd=Decimal(str(data.get("lastPrice", 0))),
                            price_btc=Decimal("0"),
                            price_eth=Decimal("0"),
                            volume_24h=Decimal(str(data.get("volume", 0))),
                            market_cap=Decimal("0"),
                            liquidity=Decimal(str(data.get("quoteVolume", 0))),
                            source=PriceSource.BINANCE,
                            timestamp=datetime.now()
                        )
            
            return None

        except Exception as e:
            logger.error(f"Erreur Binance pour {symbol}: {e}")
            return None

    async def _get_price_defi_pulse(self, symbol: str) -> Optional[TokenPrice]:
        """
        Récupère le prix depuis DeFi Pulse.

        Args:
            symbol: Symbole du token

        Returns:
            Prix du token
        """
        try:
            api_key = self.api_keys.get("defi_pulse")
            if not api_key:
                return None

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.PRICE_APIS[PriceSource.DEFI_PULSE]}/prices",
                    params={"symbol": symbol.upper()}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return TokenPrice(
                            symbol=symbol.upper(),
                            price_usd=Decimal(str(data.get("price", 0))),
                            price_btc=Decimal("0"),
                            price_eth=Decimal("0"),
                            volume_24h=Decimal("0"),
                            market_cap=Decimal("0"),
                            liquidity=Decimal("0"),
                            source=PriceSource.DEFI_PULSE,
                            timestamp=datetime.now()
                        )
            
            return None

        except Exception as e:
            logger.error(f"Erreur DeFi Pulse pour {symbol}: {e}")
            return None

    # ========================================================================
    # SNAPSHOTS ET HISTORIQUE
    # ========================================================================

    async def create_snapshot(
        self,
        wallet: BaseWallet,
        metadata: Optional[Dict] = None
    ) -> BalanceSnapshot:
        """
        Crée un snapshot du solde.

        Args:
            wallet: Wallet
            metadata: Métadonnées supplémentaires

        Returns:
            Snapshot du solde
        """
        try:
            balance = await self.get_balance(wallet, force_refresh=True)
            wallet_id = wallet.config.wallet_id
            
            snapshot = BalanceSnapshot(
                wallet_id=wallet_id,
                timestamp=datetime.now(),
                native_balance=balance.native_balance,
                native_balance_usd=balance.native_balance_usd,
                token_balances=balance.token_balances,
                token_balances_usd=balance.token_balances_usd,
                nft_balances={},
                staked_balances={},
                locked_balances={},
                total_balance_usd=balance.total_balance_usd,
                price_changes={},
                metadata=metadata or {}
            )

            # Stockage du snapshot
            if wallet_id not in self._snapshot_cache:
                self._snapshot_cache[wallet_id] = []
            
            self._snapshot_cache[wallet_id].append(snapshot)
            
            # Limite à 1000 snapshots
            if len(self._snapshot_cache[wallet_id]) > 1000:
                self._snapshot_cache[wallet_id] = self._snapshot_cache[wallet_id][-1000:]

            return snapshot

        except Exception as e:
            logger.error(f"Erreur lors de la création du snapshot: {e}")
            raise

    async def get_snapshots(
        self,
        wallet_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[BalanceSnapshot]:
        """
        Récupère les snapshots d'un wallet.

        Args:
            wallet_id: ID du wallet
            from_date: Date de début
            to_date: Date de fin
            limit: Nombre de snapshots

        Returns:
            Liste des snapshots
        """
        try:
            snapshots = self._snapshot_cache.get(wallet_id, [])
            
            if from_date:
                snapshots = [s for s in snapshots if s.timestamp >= from_date]
            
            if to_date:
                snapshots = [s for s in snapshots if s.timestamp <= to_date]
            
            # Tri du plus récent au plus ancien
            snapshots.sort(key=lambda x: x.timestamp, reverse=True)
            
            return snapshots[:limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des snapshots: {e}")
            return []

    async def get_balance_history(
        self,
        wallet_id: UUID,
        period: str = "7d",
        interval: str = "1d"
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des soldes.

        Args:
            wallet_id: ID du wallet
            period: Période (7d, 30d, 90d, 365d)
            interval: Intervalle (1h, 4h, 1d)

        Returns:
            Historique des soldes
        """
        try:
            snapshots = await self.get_snapshots(wallet_id)
            
            # Filtrage par période
            days = int(period.replace('d', ''))
            cutoff = datetime.now() - timedelta(days=days)
            snapshots = [s for s in snapshots if s.timestamp >= cutoff]
            
            # Groupement par intervalle
            history = []
            current_time = cutoff
            
            while current_time <= datetime.now():
                day_snapshots = [
                    s for s in snapshots
                    if abs((s.timestamp - current_time).total_seconds()) < 3600 * 24
                ]
                
                if day_snapshots:
                    avg_balance = sum(s.total_balance_usd for s in day_snapshots) / len(day_snapshots)
                    history.append({
                        "timestamp": current_time.isoformat(),
                        "balance_usd": float(avg_balance)
                    })
                
                current_time += timedelta(days=1)
            
            return history

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            return []

    # ========================================================================
    # ALERTES DE SOLDE
    # ========================================================================

    async def set_alert(
        self,
        wallet_id: UUID,
        user_id: UUID,
        alert_type: str,
        condition: str,
        threshold: Decimal,
        severity: str = "warning",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Configure une alerte de solde.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur
            alert_type: Type d'alerte
            condition: Condition (>, <, >=, <=, ==)
            threshold: Seuil
            severity: Sévérité
            metadata: Métadonnées

        Returns:
            Configuration de l'alerte
        """
        try:
            alert_config = {
                "alert_id": str(uuid4()),
                "wallet_id": str(wallet_id),
                "user_id": str(user_id),
                "type": alert_type,
                "condition": condition,
                "threshold": str(threshold),
                "severity": severity,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }

            if wallet_id not in self._alert_configs:
                self._alert_configs[wallet_id] = []
            
            self._alert_configs[wallet_id].append(alert_config)

            logger.info(f"Alerte configurée pour {wallet_id}: {alert_type} {condition} {threshold}")
            return alert_config

        except Exception as e:
            logger.error(f"Erreur lors de la configuration de l'alerte: {e}")
            return {}

    async def check_alerts(
        self,
        wallet: BaseWallet,
        force_check: bool = False
    ) -> List[BalanceAlert]:
        """
        Vérifie les alertes pour un wallet.

        Args:
            wallet: Wallet
            force_check: Forcer la vérification

        Returns:
            Liste des alertes déclenchées
        """
        try:
            wallet_id = wallet.config.wallet_id
            alerts = []
            
            if wallet_id not in self._alert_configs:
                return []

            balance = await self.get_balance(wallet, force_refresh=force_check)
            total_usd = balance.total_balance_usd

            for config in self._alert_configs[wallet_id]:
                threshold = Decimal(config["threshold"])
                condition = config["condition"]
                
                triggered = False
                current_value = total_usd

                if condition == ">":
                    triggered = total_usd > threshold
                elif condition == ">=":
                    triggered = total_usd >= threshold
                elif condition == "<":
                    triggered = total_usd < threshold
                elif condition == "<=":
                    triggered = total_usd <= threshold
                elif condition == "==":
                    triggered = total_usd == threshold

                if triggered:
                    alert = BalanceAlert(
                        alert_id=UUID(config["alert_id"]),
                        wallet_id=wallet_id,
                        user_id=UUID(config["user_id"]),
                        type=config["type"],
                        condition=condition,
                        current_value=current_value,
                        threshold_value=threshold,
                        severity=config["severity"],
                        message=f"Solde {condition} {threshold}: {current_value:.2f} USD",
                        timestamp=datetime.now(),
                        metadata=config.get("metadata", {})
                    )
                    alerts.append(alert)
                    
                    self._metrics["total_alerts_triggered"] += 1

            # Stockage des alertes
            if wallet_id not in self._alert_cache:
                self._alert_cache[wallet_id] = []
            
            self._alert_cache[wallet_id].extend(alerts)

            return alerts

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des alertes: {e}")
            return []

    async def get_alerts(
        self,
        wallet_id: UUID,
        acknowledged: Optional[bool] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[BalanceAlert]:
        """
        Récupère les alertes d'un wallet.

        Args:
            wallet_id: ID du wallet
            acknowledged: Filtrer par statut
            severity: Filtrer par sévérité
            limit: Nombre d'alertes

        Returns:
            Liste des alertes
        """
        try:
            alerts = self._alert_cache.get(wallet_id, [])
            
            if acknowledged is not None:
                alerts = [a for a in alerts if a.acknowledged == acknowledged]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            alerts.sort(key=lambda x: x.timestamp, reverse=True)
            
            return alerts[:limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des alertes: {e}")
            return []

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
        try:
            for wallet_alerts in self._alert_cache.values():
                for alert in wallet_alerts:
                    if alert.alert_id == alert_id:
                        alert.acknowledged = True
                        logger.info(f"Alerte {alert_id} reconnue")
                        return True
            
            return False

        except Exception as e:
            logger.error(f"Erreur lors de la reconnaissance de l'alerte: {e}")
            return False

    # ========================================================================
    # NFTs ET COLLECTIONS
    # ========================================================================

    async def _get_nft_balances(self, wallet: BaseWallet) -> List[Dict[str, Any]]:
        """
        Récupère les NFTs d'un wallet.

        Args:
            wallet: Wallet

        Returns:
            Liste des NFTs
        """
        # Pour l'implémentation complète, utiliser les APIs NFT
        # OpenSea, Rarible, etc.
        return []

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_balance_summary(
        self,
        wallet: BaseWallet
    ) -> Dict[str, Any]:
        """
        Récupère un résumé des soldes.

        Args:
            wallet: Wallet

        Returns:
            Résumé des soldes
        """
        try:
            balance = await self.get_balance(wallet, force_refresh=True)
            
            # Calcul des métriques
            total_tokens = len(balance.token_balances)
            token_value = sum(balance.token_balances_usd.values())
            
            return {
                "wallet_id": str(wallet.config.wallet_id),
                "address": wallet.config.address,
                "blockchain": wallet.config.blockchain,
                "native": {
                    "balance": float(balance.native_balance),
                    "usd": float(balance.native_balance_usd)
                },
                "tokens": {
                    "count": total_tokens,
                    "usd": float(token_value)
                },
                "total": {
                    "usd": float(balance.total_balance_usd)
                },
                "last_updated": balance.last_updated.isoformat(),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du résumé: {e}")
            return {}

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_balances_checked": self._metrics["total_balances_checked"],
                "total_alerts_triggered": self._metrics["total_alerts_triggered"],
                "total_price_updates": self._metrics["total_price_updates"],
                "last_check": self._metrics["last_check"],
                "last_price_update": self._metrics["last_price_update"],
                "cached_balances": len(self._balance_cache),
                "cached_prices": len(self._price_cache),
                "active_alerts": sum(len(a) for a in self._alert_configs.values()),
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
        logger.info("Fermeture de WalletBalanceService...")
        self._balance_cache.clear()
        self._price_cache.clear()
        self._snapshot_cache.clear()
        self._alert_cache.clear()
        self._alert_configs.clear()
        logger.info("WalletBalanceService fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_balance_service(
    api_keys: Optional[Dict[str, str]] = None,
    redis_url: str = "redis://localhost:6379/0"
) -> WalletBalanceService:
    """
    Crée une instance du service de gestion des soldes.

    Args:
        api_keys: Clés API pour les services externes
        redis_url: URL de connexion Redis

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletBalanceService(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BalanceType",
    "PriceSource",
    "TokenPrice",
    "BalanceSnapshot",
    "BalanceAlert",
    "WalletBalanceService",
    "create_wallet_balance_service"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de gestion des soldes."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET BALANCE MODULE")
    print("=" * 60)

    # Création du service
    balance_service = create_wallet_balance_service(
        api_keys={
            "coinmarketcap": "YOUR_CMC_API_KEY",
            "defi_pulse": "YOUR_DEFI_PULSE_API_KEY"
        }
    )

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Balance Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Récupération du solde
    balance = await balance_service.get_balance(wallet)
    print(f"\n💰 Solde:")
    print(f"   ETH: {balance.native_balance} (${balance.native_balance_usd:.2f})")
    print(f"   Total: ${balance.total_balance_usd:.2f}")

    # Récupération du prix d'un token
    price = await balance_service.get_token_price("eth")
    if price:
        print(f"\n📊 Prix ETH:")
        print(f"   USD: ${price.price_usd:.2f}")
        print(f"   Volume 24h: ${price.volume_24h:,.0f}")
        print(f"   Market Cap: ${price.market_cap:,.0f}")

    # Création d'un snapshot
    snapshot = await balance_service.create_snapshot(wallet)
    print(f"\n📸 Snapshot créé à {snapshot.timestamp}")
    print(f"   Solde total: ${snapshot.total_balance_usd:.2f}")

    # Configuration d'une alerte
    alert_config = await balance_service.set_alert(
        wallet_id=wallet.config.wallet_id,
        user_id=user_id,
        alert_type="balance",
        condition="<",
        threshold=Decimal("100"),
        severity="critical",
        metadata={"notification": "email"}
    )
    print(f"\n🔔 Alerte configurée:")
    print(f"   ID: {alert_config['alert_id']}")
    print(f"   Condition: < 100 USD")

    # Vérification des alertes
    alerts = await balance_service.check_alerts(wallet, force_check=True)
    if alerts:
        print(f"\n⚠️ Alertes déclenchées:")
        for alert in alerts:
            print(f"   [{alert.severity.upper()}] {alert.message}")
    else:
        print(f"\n✅ Aucune alerte déclenchée")

    # Historique des soldes
    history = await balance_service.get_balance_history(
        wallet.config.wallet_id,
        period="7d"
    )
    print(f"\n📈 Historique (7 jours):")
    for entry in history[:5]:
        print(f"   {entry['timestamp'][:10]}: ${entry['balance_usd']:.2f}")

    # Santé du service
    health = await balance_service.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Balances vérifiées: {health['total_balances_checked']}")
    print(f"   Alertes déclenchées: {health['total_alerts_triggered']}")
    print(f"   Prix mis à jour: {health['total_price_updates']}")

    # Fermeture
    await balance_service.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletBalanceService NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

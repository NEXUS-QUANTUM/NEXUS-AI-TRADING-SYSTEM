"""
NEXUS AI TRADING SYSTEM - HEDGE BOT COLLATERAL MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des collatéraux pour le Hedge Bot.
Gestion des garanties, ratios, liquidations, et optimisation des collatéraux.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_volatility,
    calculate_var,
    calculate_expected_shortfall
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class CollateralType(Enum):
    """Types de collatéraux."""
    CASH = "cash"
    CRYPTO = "crypto"
    STABLE = "stable"
    STOCK = "stock"
    BOND = "bond"
    COMMODITY = "commodity"
    NFT = "nft"
    REAL_ESTATE = "real_estate"
    OTHER = "other"


class CollateralStatus(Enum):
    """Statuts de collatéral."""
    ACTIVE = "active"
    LOCKED = "locked"
    PENDING = "pending"
    RELEASED = "released"
    LIQUIDATED = "liquidated"
    WITHDRAWN = "withdrawn"


class LiquidationStatus(Enum):
    """Statuts de liquidation."""
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"
    LIQUIDATING = "liquidating"
    LIQUIDATED = "liquidated"
    PARTIAL = "partial"


@dataclass
class Collateral:
    """Collatéral."""
    collateral_id: UUID
    user_id: UUID
    asset: str
    amount: Decimal
    value_usd: Decimal
    collateral_type: CollateralType
    status: CollateralStatus
    locked_until: Optional[datetime] = None
    liquidation_price: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "collateral_id": str(self.collateral_id),
            "user_id": str(self.user_id),
            "asset": self.asset,
            "amount": str(self.amount),
            "value_usd": str(self.value_usd),
            "collateral_type": self.collateral_type.value,
            "status": self.status.value,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None,
            "liquidation_price": str(self.liquidation_price) if self.liquidation_price else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class CollateralPosition:
    """Position de collatéral."""
    position_id: UUID
    user_id: UUID
    collateral: Collateral
    debt: Decimal
    debt_usd: Decimal
    loan_to_value: float
    liquidation_threshold: float
    margin_call_threshold: float
    health_factor: float
    status: CollateralStatus
    liquidation_status: LiquidationStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "collateral": self.collateral.to_dict(),
            "debt": str(self.debt),
            "debt_usd": str(self.debt_usd),
            "loan_to_value": self.loan_to_value,
            "liquidation_threshold": self.liquidation_threshold,
            "margin_call_threshold": self.margin_call_threshold,
            "health_factor": self.health_factor,
            "status": self.status.value,
            "liquidation_status": self.liquidation_status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class CollateralMetrics:
    """Métriques de collatéral."""
    user_id: UUID
    total_collateral_usd: Decimal
    total_debt_usd: Decimal
    total_equity_usd: Decimal
    weighted_ltv: float
    health_factor: float
    liquidation_risk: float
    margin_used: float
    available_margin: Decimal
    collateral_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "total_collateral_usd": str(self.total_collateral_usd),
            "total_debt_usd": str(self.total_debt_usd),
            "total_equity_usd": str(self.total_equity_usd),
            "weighted_ltv": self.weighted_ltv,
            "health_factor": self.health_factor,
            "liquidation_risk": self.liquidation_risk,
            "margin_used": self.margin_used,
            "available_margin": str(self.available_margin),
            "collateral_ratio": self.collateral_ratio,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE COLLATERAL MANAGER
# ============================================================================

class CollateralManager:
    """
    Gestionnaire de collatéraux avancé.
    """

    # Ratios par défaut
    DEFAULT_LTV_RATIOS = {
        "crypto": 0.70,
        "stable": 0.90,
        "cash": 0.95,
        "stock": 0.50,
        "bond": 0.80
    }

    # Seuils de liquidation
    DEFAULT_LIQUIDATION_THRESHOLDS = {
        "crypto": 0.80,
        "stable": 0.95,
        "cash": 0.98,
        "stock": 0.65,
        "bond": 0.85
    }

    # Décotes par type
    DEFAULT_HAIRCUTS = {
        "crypto": 0.20,
        "stable": 0.05,
        "cash": 0.02,
        "stock": 0.30,
        "bond": 0.15
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de collatéraux.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._collateral_cache: Dict[UUID, Collateral] = {}
        self._position_cache: Dict[UUID, CollateralPosition] = {}
        self._metrics_cache: Dict[UUID, CollateralMetrics] = {}
        self._price_cache: Dict[str, Decimal] = {}
        
        # Métriques
        self._metrics = {
            "total_collateral": Decimal("0"),
            "total_debt": Decimal("0"),
            "total_liquidations": 0,
            "total_margin_calls": 0,
            "by_type": {},
            "by_status": {},
            "last_update": None
        }

        logger.info("CollateralManager initialisé avec succès")

    # ========================================================================
    # GESTION DES COLLATÉRAUX
    # ========================================================================

    async def add_collateral(
        self,
        user_id: UUID,
        asset: str,
        amount: Decimal,
        collateral_type: CollateralType,
        value_usd: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> Collateral:
        """
        Ajoute un collatéral.

        Args:
            user_id: ID de l'utilisateur
            asset: Actif
            amount: Montant
            collateral_type: Type de collatéral
            value_usd: Valeur en USD
            metadata: Métadonnées

        Returns:
            Collatéral ajouté
        """
        try:
            collateral_id = uuid4()
            now = datetime.now()

            if value_usd is None:
                price = await self._get_price(asset)
                value_usd = amount * price

            collateral = Collateral(
                collateral_id=collateral_id,
                user_id=user_id,
                asset=asset,
                amount=amount,
                value_usd=value_usd,
                collateral_type=collateral_type,
                status=CollateralStatus.ACTIVE,
                metadata=metadata or {}
            )

            self._collateral_cache[collateral_id] = collateral
            self._metrics["total_collateral"] += value_usd

            collateral_type_key = collateral_type.value
            if collateral_type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][collateral_type_key] = 0
            self._metrics["by_type"][collateral_type_key] += 1

            return collateral

        except Exception as e:
            logger.error(f"Erreur d'ajout de collatéral: {e}")
            raise

    async def remove_collateral(
        self,
        collateral_id: UUID,
        amount: Optional[Decimal] = None
    ) -> bool:
        """
        Retire un collatéral.

        Args:
            collateral_id: ID du collatéral
            amount: Montant à retirer

        Returns:
            True si retiré
        """
        try:
            collateral = self._collateral_cache.get(collateral_id)
            if not collateral:
                return False

            if amount is None or amount >= collateral.amount:
                # Retrait total
                self._metrics["total_collateral"] -= collateral.value_usd
                del self._collateral_cache[collateral_id]
            else:
                # Retrait partiel
                ratio = amount / collateral.amount
                collateral.amount -= amount
                collateral.value_usd -= collateral.value_usd * ratio
                self._metrics["total_collateral"] -= collateral.value_usd * ratio

            return True

        except Exception as e:
            logger.error(f"Erreur de retrait de collatéral: {e}")
            return False

    # ========================================================================
    # GESTION DES POSITIONS
    # ========================================================================

    async def create_position(
        self,
        user_id: UUID,
        collateral_id: UUID,
        debt: Decimal,
        debt_usd: Decimal,
        loan_to_value: Optional[float] = None,
        liquidation_threshold: Optional[float] = None,
        margin_call_threshold: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> CollateralPosition:
        """
        Crée une position de collatéral.

        Args:
            user_id: ID de l'utilisateur
            collateral_id: ID du collatéral
            debt: Dette
            debt_usd: Dette en USD
            loan_to_value: Ratio LTV
            liquidation_threshold: Seuil de liquidation
            margin_call_threshold: Seuil d'appel de marge
            metadata: Métadonnées

        Returns:
            Position créée
        """
        try:
            collateral = await self.get_collateral(collateral_id)
            if not collateral:
                raise ValueError(f"Collatéral {collateral_id} non trouvé")

            position_id = uuid4()
            now = datetime.now()

            # Calcul des ratios
            if loan_to_value is None:
                loan_to_value = self.DEFAULT_LTV_RATIOS.get(
                    collateral.collateral_type.value,
                    0.70
                )

            if liquidation_threshold is None:
                liquidation_threshold = self.DEFAULT_LIQUIDATION_THRESHOLDS.get(
                    collateral.collateral_type.value,
                    0.80
                )

            if margin_call_threshold is None:
                margin_call_threshold = liquidation_threshold * 0.8

            # Calcul du health factor
            health_factor = collateral.value_usd / debt_usd if debt_usd > 0 else 999
            health_factor = min(float(health_factor), 10.0)

            position = CollateralPosition(
                position_id=position_id,
                user_id=user_id,
                collateral=collateral,
                debt=debt,
                debt_usd=debt_usd,
                loan_to_value=loan_to_value,
                liquidation_threshold=liquidation_threshold,
                margin_call_threshold=margin_call_threshold,
                health_factor=health_factor,
                status=CollateralStatus.ACTIVE,
                liquidation_status=LiquidationStatus.NONE,
                metadata=metadata or {}
            )

            self._position_cache[position_id] = position
            self._metrics["total_debt"] += debt_usd

            return position

        except Exception as e:
            logger.error(f"Erreur de création de position: {e}")
            raise

    async def update_position(
        self,
        position_id: UUID,
        debt: Optional[Decimal] = None,
        debt_usd: Optional[Decimal] = None,
        collateral_value: Optional[Decimal] = None
    ) -> Optional[CollateralPosition]:
        """
        Met à jour une position.

        Args:
            position_id: ID de la position
            debt: Nouvelle dette
            debt_usd: Nouvelle dette en USD
            collateral_value: Nouvelle valeur du collatéral

        Returns:
            Position mise à jour
        """
        try:
            position = self._position_cache.get(position_id)
            if not position:
                return None

            if debt is not None:
                position.debt = debt

            if debt_usd is not None:
                position.debt_usd = debt_usd

            if collateral_value is not None:
                position.collateral.value_usd = collateral_value

            # Mise à jour des métriques
            health_factor = position.collateral.value_usd / position.debt_usd if position.debt_usd > 0 else 999
            position.health_factor = min(float(health_factor), 10.0)

            # Vérification du health factor
            await self._check_health_factor(position)

            position.updated_at = datetime.now()
            return position

        except Exception as e:
            logger.error(f"Erreur de mise à jour de position: {e}")
            return None

    async def _check_health_factor(
        self,
        position: CollateralPosition
    ) -> None:
        """
        Vérifie le health factor et déclenche des actions.

        Args:
            position: Position à vérifier
        """
        try:
            # Vérification du seuil de liquidation
            if position.health_factor <= position.liquidation_threshold:
                position.liquidation_status = LiquidationStatus.LIQUIDATING
                self._metrics["total_liquidations"] += 1
                logger.warning(
                    f"Liquidation déclenchée pour {position.position_id} "
                    f"(health factor: {position.health_factor:.2f})"
                )
                await self._liquidate(position)

            # Vérification de l'appel de marge
            elif position.health_factor <= position.margin_call_threshold:
                position.liquidation_status = LiquidationStatus.CRITICAL
                self._metrics["total_margin_calls"] += 1
                logger.warning(
                    f"Appel de marge pour {position.position_id} "
                    f"(health factor: {position.health_factor:.2f})"
                )
                await self._margin_call(position)

            elif position.health_factor <= position.margin_call_threshold * 1.2:
                position.liquidation_status = LiquidationStatus.WARNING
            else:
                position.liquidation_status = LiquidationStatus.NONE

        except Exception as e:
            logger.error(f"Erreur de vérification du health factor: {e}")

    async def _liquidate(self, position: CollateralPosition) -> None:
        """
        Liquide une position.

        Args:
            position: Position à liquider
        """
        try:
            # Liquidation du collatéral
            position.status = CollateralStatus.LIQUIDATED
            position.liquidation_status = LiquidationStatus.LIQUIDATED
            position.updated_at = datetime.now()

            # Log de la liquidation
            logger.info(
                f"Position {position.position_id} liquidée - "
                f"Collatéral: {position.collateral.value_usd} USD, "
                f"Dette: {position.debt_usd} USD"
            )

        except Exception as e:
            logger.error(f"Erreur de liquidation: {e}")

    async def _margin_call(self, position: CollateralPosition) -> None:
        """
        Déclenche un appel de marge.

        Args:
            position: Position concernée
        """
        try:
            # Notification d'appel de marge
            logger.info(
                f"Appel de marge pour {position.position_id} - "
                f"Health factor: {position.health_factor:.2f}, "
                f"Seuil: {position.margin_call_threshold:.2f}"
            )

            # Ici, envoyer une notification (email, SMS, etc.)
            # Pour l'exemple, on log simplement

        except Exception as e:
            logger.error(f"Erreur d'appel de marge: {e}")

    # ========================================================================
    # MÉTRIQUES
    # ========================================================================

    async def get_metrics(
        self,
        user_id: UUID
    ) -> CollateralMetrics:
        """
        Récupère les métriques de collatéral.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Métriques
        """
        try:
            positions = [
                p for p in self._position_cache.values()
                if p.user_id == user_id
            ]

            if not positions:
                return CollateralMetrics(
                    user_id=user_id,
                    total_collateral_usd=Decimal("0"),
                    total_debt_usd=Decimal("0"),
                    total_equity_usd=Decimal("0"),
                    weighted_ltv=0.0,
                    health_factor=0.0,
                    liquidation_risk=0.0,
                    margin_used=0.0,
                    available_margin=Decimal("0"),
                    collateral_ratio=0.0
                )

            total_collateral = sum(p.collateral.value_usd for p in positions)
            total_debt = sum(p.debt_usd for p in positions)
            total_equity = total_collateral - total_debt

            # LTV pondéré
            weighted_ltv = float(total_debt / total_collateral) if total_collateral > 0 else 0

            # Health factor moyen
            avg_health_factor = sum(p.health_factor for p in positions) / len(positions)

            # Risque de liquidation
            liquidation_risk = sum(
                1 for p in positions
                if p.liquidation_status != LiquidationStatus.NONE
            ) / len(positions)

            # Marge disponible
            margin_used = float(total_debt / total_collateral) if total_collateral > 0 else 0
            available_margin = total_collateral * Decimal(str(1 - margin_used))

            # Ratio de collatéral
            collateral_ratio = float(total_collateral / total_debt) if total_debt > 0 else 0

            return CollateralMetrics(
                user_id=user_id,
                total_collateral_usd=total_collateral,
                total_debt_usd=total_debt,
                total_equity_usd=total_equity,
                weighted_ltv=weighted_ltv,
                health_factor=avg_health_factor,
                liquidation_risk=liquidation_risk,
                margin_used=margin_used,
                available_margin=available_margin,
                collateral_ratio=collateral_ratio
            )

        except Exception as e:
            logger.error(f"Erreur de récupération des métriques: {e}")
            return CollateralMetrics(user_id=user_id)

    # ========================================================================
    # OPTIMISATION
    # ========================================================================

    async def optimize_collateral(
        self,
        user_id: UUID,
        target_ltv: float = 0.60,
        risk_tolerance: float = 0.10
    ) -> Dict[str, Any]:
        """
        Optimise l'utilisation des collatéraux.

        Args:
            user_id: ID de l'utilisateur
            target_ltv: LTV cible
            risk_tolerance: Tolérance au risque

        Returns:
            Recommandations d'optimisation
        """
        try:
            positions = [
                p for p in self._position_cache.values()
                if p.user_id == user_id
            ]

            if not positions:
                return {"error": "Aucune position trouvée"}

            metrics = await self.get_metrics(user_id)

            recommendations = []

            # Analyse des positions
            for position in positions:
                current_ltv = float(position.debt_usd / position.collateral.value_usd) if position.collateral.value_usd > 0 else 0

                if current_ltv > target_ltv + risk_tolerance:
                    recommendations.append({
                        "position_id": str(position.position_id),
                        "action": "reduce_debt",
                        "current_ltv": current_ltv,
                        "target_ltv": target_ltv,
                        "amount_to_reduce": position.debt_usd - (position.collateral.value_usd * Decimal(str(target_ltv))),
                        "priority": "high" if current_ltv > position.liquidation_threshold else "medium"
                    })

                elif current_ltv < target_ltv - risk_tolerance:
                    recommendations.append({
                        "position_id": str(position.position_id),
                        "action": "increase_leverage",
                        "current_ltv": current_ltv,
                        "target_ltv": target_ltv,
                        "potential_borrow": (position.collateral.value_usd * Decimal(str(target_ltv))) - position.debt_usd,
                        "priority": "low"
                    })

            # Analyse globale
            if metrics.weighted_ltv > target_ltv + risk_tolerance:
                recommendations.append({
                    "action": "global_reduce",
                    "current_ltv": metrics.weighted_ltv,
                    "target_ltv": target_ltv,
                    "total_reduction_needed": metrics.total_debt_usd - (metrics.total_collateral_usd * Decimal(str(target_ltv))),
                    "priority": "high"
                })

            return {
                "metrics": metrics.to_dict(),
                "recommendations": recommendations,
                "total_positions": len(positions),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'optimisation: {e}")
            return {"error": str(e)}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_collateral(
        self,
        collateral_id: UUID
    ) -> Optional[Collateral]:
        """
        Récupère un collatéral.

        Args:
            collateral_id: ID du collatéral

        Returns:
            Collatéral ou None
        """
        return self._collateral_cache.get(collateral_id)

    async def get_position(
        self,
        position_id: UUID
    ) -> Optional[CollateralPosition]:
        """
        Récupère une position.

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        return self._position_cache.get(position_id)

    async def get_positions(
        self,
        user_id: UUID,
        status: Optional[CollateralStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[CollateralPosition]:
        """
        Récupère les positions d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            status: Filtrer par statut
            limit: Nombre de positions
            offset: Décalage

        Returns:
            Liste des positions
        """
        positions = [
            p for p in self._position_cache.values()
            if p.user_id == user_id
        ]

        if status:
            positions = [p for p in positions if p.status == status]

        positions.sort(key=lambda x: x.created_at, reverse=True)
        return positions[offset:offset + limit]

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    async def _get_price(self, asset: str) -> Decimal:
        """
        Récupère le prix d'un actif.

        Args:
            asset: Actif

        Returns:
            Prix
        """
        if asset in self._price_cache:
            return self._price_cache[asset]

        # Simulation de prix
        price = Decimal("100")  # Valeur par défaut
        self._price_cache[asset] = price
        return price

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
                "total_collateral": str(self._metrics["total_collateral"]),
                "total_debt": str(self._metrics["total_debt"]),
                "total_liquidations": self._metrics["total_liquidations"],
                "total_margin_calls": self._metrics["total_margin_calls"],
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_update": self._metrics["last_update"],
                "cached_collaterals": len(self._collateral_cache),
                "cached_positions": len(self._position_cache),
                "cached_prices": len(self._price_cache),
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
        logger.info("Fermeture de CollateralManager...")
        self._collateral_cache.clear()
        self._position_cache.clear()
        self._metrics_cache.clear()
        self._price_cache.clear()
        logger.info("CollateralManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_collateral_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> CollateralManager:
    """
    Crée une instance de CollateralManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de CollateralManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return CollateralManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "CollateralType",
    "CollateralStatus",
    "LiquidationStatus",
    "Collateral",
    "CollateralPosition",
    "CollateralMetrics",
    "CollateralManager",
    "create_collateral_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du CollateralManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT COLLATERAL MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    collateral_mgr = create_collateral_manager()

    print(f"\n✅ CollateralManager initialisé")

    # Ajout d'un collatéral
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n💰 Ajout d'un collatéral...")
    
    collateral = await collateral_mgr.add_collateral(
        user_id=user_id,
        asset="BTC",
        amount=Decimal("0.5"),
        collateral_type=CollateralType.CRYPTO,
        value_usd=Decimal("25000")
    )

    print(f"   ID: {collateral.collateral_id}")
    print(f"   Actif: {collateral.asset}")
    print(f"   Montant: {collateral.amount}")
    print(f"   Valeur: ${collateral.value_usd}")

    # Création d'une position
    print(f"\n📊 Création d'une position...")
    position = await collateral_mgr.create_position(
        user_id=user_id,
        collateral_id=collateral.collateral_id,
        debt=Decimal("0.1"),
        debt_usd=Decimal("5000"),
        loan_to_value=0.70,
        liquidation_threshold=0.80
    )

    print(f"   ID: {position.position_id}")
    print(f"   Dette: ${position.debt_usd}")
    print(f"   LTV: {position.loan_to_value:.2f}")
    print(f"   Health factor: {position.health_factor:.2f}")

    # Métriques
    print(f"\n📈 Métriques de collatéral:")
    metrics = await collateral_mgr.get_metrics(user_id)
    print(f"   Collatéral total: ${metrics.total_collateral_usd}")
    print(f"   Dette totale: ${metrics.total_debt_usd}")
    print(f"   Equity: ${metrics.total_equity_usd}")
    print(f"   LTV pondéré: {metrics.weighted_ltv:.2f}")
    print(f"   Health factor: {metrics.health_factor:.2f}")
    print(f"   Marge disponible: ${metrics.available_margin}")

    # Optimisation
    print(f"\n🎯 Optimisation du collatéral...")
    optimization = await collateral_mgr.optimize_collateral(
        user_id=user_id,
        target_ltv=0.60
    )

    print(f"   Recommandations: {len(optimization.get('recommendations', []))}")
    for rec in optimization.get('recommendations', [])[:3]:
        print(f"      {rec.get('action')}: LTV {rec.get('current_ltv', 0):.2f} -> {rec.get('target_ltv', 0):.2f}")

    # Santé du service
    health = await collateral_mgr.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Collatéral total: ${health['total_collateral']}")
    print(f"   Liquidations: {health['total_liquidations']}")

    # Fermeture
    await collateral_mgr.close()

    print("\n" + "=" * 60)
    print("CollateralManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

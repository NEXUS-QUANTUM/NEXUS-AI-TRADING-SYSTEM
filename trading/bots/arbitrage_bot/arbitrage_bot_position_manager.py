"""
NEXUS AI TRADING SYSTEM - ARBITRAGE BOT POSITION MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des positions pour le bot d'arbitrage.
Gestion des positions, suivi PnL, risk management, et reporting.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import numpy as np
from scipy import stats

from ..arbitrage_bot import (
    ArbitrageBot,
    ArbitrageOpportunity,
    ArbitrageConfig,
    ExchangeType,
    ArbitrageType,
    ArbitrageStatus
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class PositionStatus(Enum):
    """Statuts de position."""
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    PARTIALLY_CLOSED = "partially_closed"
    PENDING = "pending"
    ERROR = "error"


class PositionType(Enum):
    """Types de position."""
    LONG = "long"
    SHORT = "short"
    HEDGED = "hedged"
    SPREAD = "spread"
    ARBITRAGE = "arbitrage"


@dataclass
class PositionMetrics:
    """Métriques de position."""
    position_id: UUID
    total_pnl: Decimal
    total_pnl_usd: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    total_volume: Decimal
    max_drawdown: float
    max_profit: float
    average_entry: Decimal
    average_exit: Decimal
    holding_period: float  # Heures
    roi_percentage: float
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    recovery_factor: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "total_pnl": str(self.total_pnl),
            "total_pnl_usd": str(self.total_pnl_usd),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "total_fees": str(self.total_fees),
            "total_volume": str(self.total_volume),
            "max_drawdown": self.max_drawdown,
            "max_profit": self.max_profit,
            "average_entry": str(self.average_entry),
            "average_exit": str(self.average_exit),
            "holding_period": self.holding_period,
            "roi_percentage": self.roi_percentage,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "recovery_factor": self.recovery_factor,
            "metadata": self.metadata
        }


@dataclass
class RiskMetrics:
    """Métriques de risque."""
    position_id: UUID
    value_at_risk_95: Decimal
    value_at_risk_99: Decimal
    expected_shortfall: Decimal
    max_drawdown: float
    current_drawdown: float
    volatility: float
    beta: float
    alpha: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_ratio: float
    risk_reward_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "value_at_risk_95": str(self.value_at_risk_95),
            "value_at_risk_99": str(self.value_at_risk_99),
            "expected_shortfall": str(self.expected_shortfall),
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "volatility": self.volatility,
            "beta": self.beta,
            "alpha": self.alpha,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "var_ratio": self.var_ratio,
            "risk_reward_ratio": self.risk_reward_ratio,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE POSITION MANAGER
# ============================================================================

class ArbitrageBotPositionManager:
    """
    Gestionnaire de positions pour le bot d'arbitrage.
    """

    # Seuils de risque par défaut
    DEFAULT_RISK_LIMITS = {
        "max_position_size": Decimal("10000"),
        "max_leverage": 3.0,
        "max_drawdown": 0.15,
        "min_roi": 0.005,
        "max_exposure": 0.5,
        "stop_loss": 0.05,
        "take_profit": 0.15,
        "trailing_stop": 0.02,
        "max_daily_loss": Decimal("1000")
    }

    # Paramètres de calcul de VaR
    VAR_CONFIDENCE_LEVELS = [0.95, 0.99]
    VAR_HISTORICAL_DAYS = 30

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        risk_limits: Optional[Dict[str, Any]] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le gestionnaire de positions.

        Args:
            redis_client: Client Redis pour le cache
            risk_limits: Limites de risque
            api_keys: Clés API
        """
        self.redis = redis_client
        self.risk_limits = risk_limits or self.DEFAULT_RISK_LIMITS
        self.api_keys = api_keys or {}
        
        # Cache
        self._positions: Dict[UUID, Dict[str, Any]] = {}
        self._metrics_cache: Dict[UUID, PositionMetrics] = {}
        self._risk_metrics_cache: Dict[UUID, RiskMetrics] = {}
        
        # Positions actives
        self._active_positions: Set[UUID] = set()
        self._closed_positions: List[UUID] = []
        
        # Historique des prix
        self._price_history: Dict[str, List[Decimal]] = {}
        
        # Métriques
        self._metrics = {
            "total_positions": 0,
            "active_positions": 0,
            "closed_positions": 0,
            "total_pnl_usd": Decimal("0"),
            "total_fees_usd": Decimal("0"),
            "total_volume_usd": Decimal("0"),
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "average_roi": 0.0,
            "max_drawdown": 0.0,
            "best_trade": Decimal("0"),
            "worst_trade": Decimal("0"),
            "by_type": {},
            "by_status": {}
        }

        logger.info("ArbitrageBotPositionManager initialisé avec succès")

    # ========================================================================
    # CRÉATION ET GESTION DES POSITIONS
    # ========================================================================

    async def create_position(
        self,
        bot_id: UUID,
        exchange: ExchangeType,
        symbol: str,
        position_type: PositionType,
        side: str,  # "long" or "short"
        entry_price: Decimal,
        quantity: Decimal,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        trailing_stop: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Crée une nouvelle position.

        Args:
            bot_id: ID du bot
            exchange: Exchange
            symbol: Symbole
            position_type: Type de position
            side: Côté
            entry_price: Prix d'entrée
            quantity: Quantité
            stop_loss: Stop loss
            take_profit: Take profit
            trailing_stop: Trailing stop
            metadata: Métadonnées

        Returns:
            Position créée
        """
        try:
            # Validation
            if quantity <= 0:
                raise ValueError("La quantité doit être positive")
            
            if entry_price <= 0:
                raise ValueError("Le prix d'entrée doit être positif")

            # Vérification des limites de risque
            await self._check_risk_limits(bot_id, quantity, entry_price)

            position_id = uuid4()
            
            position = {
                "position_id": str(position_id),
                "bot_id": str(bot_id),
                "exchange": exchange.value,
                "symbol": symbol,
                "type": position_type.value,
                "side": side,
                "entry_price": str(entry_price),
                "current_price": str(entry_price),
                "quantity": str(quantity),
                "entry_value": str(entry_price * quantity),
                "current_value": str(entry_price * quantity),
                "stop_loss": str(stop_loss) if stop_loss else None,
                "take_profit": str(take_profit) if take_profit else None,
                "trailing_stop": str(trailing_stop) if trailing_stop else None,
                "highest_price": str(entry_price),
                "lowest_price": str(entry_price),
                "unrealized_pnl": "0",
                "unrealized_pnl_percent": 0.0,
                "realized_pnl": "0",
                "realized_pnl_percent": 0.0,
                "total_fees": "0",
                "status": PositionStatus.OPEN.value,
                "opened_at": datetime.now().isoformat(),
                "closed_at": None,
                "orders": [],
                "metadata": metadata or {}
            }

            # Stockage
            self._positions[position_id] = position
            self._active_positions.add(position_id)

            # Mise à jour des métriques
            self._metrics["total_positions"] += 1
            self._metrics["active_positions"] += 1

            pos_type = position_type.value
            if pos_type not in self._metrics["by_type"]:
                self._metrics["by_type"][pos_type] = 0
            self._metrics["by_type"][pos_type] += 1

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_position(position_id)

            logger.info(f"Position créée: {position_id} pour {bot_id}")
            return position

        except Exception as e:
            logger.error(f"Erreur lors de la création de la position: {e}")
            raise

    async def update_position(
        self,
        position_id: UUID,
        current_price: Decimal,
        update_orders: bool = True
    ) -> Dict[str, Any]:
        """
        Met à jour une position.

        Args:
            position_id: ID de la position
            current_price: Prix actuel
            update_orders: Mettre à jour les ordres

        Returns:
            Position mise à jour
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                raise ValueError(f"Position {position_id} non trouvée")

            entry_price = Decimal(position["entry_price"])
            quantity = Decimal(position["quantity"])
            
            # Mise à jour des prix
            old_price = Decimal(position["current_price"])
            position["current_price"] = str(current_price)
            position["current_value"] = str(current_price * quantity)

            # Mise à jour des extrêmes
            highest = Decimal(position["highest_price"])
            lowest = Decimal(position["lowest_price"])
            
            if current_price > highest:
                position["highest_price"] = str(current_price)
            if current_price < lowest:
                position["lowest_price"] = str(current_price)

            # Calcul du PnL non réalisé
            if position["side"] == "long":
                unrealized_pnl = (current_price - entry_price) * quantity
            else:
                unrealized_pnl = (entry_price - current_price) * quantity

            position["unrealized_pnl"] = str(unrealized_pnl)
            position["unrealized_pnl_percent"] = float(unrealized_pnl / (entry_price * quantity) * 100) if (entry_price * quantity) > 0 else 0

            # Vérification des stops
            await self._check_stops(position_id, current_price)

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_position(position_id)

            return position

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la position: {e}")
            raise

    async def close_position(
        self,
        position_id: UUID,
        exit_price: Decimal,
        exit_quantity: Optional[Decimal] = None,
        orders: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Ferme une position.

        Args:
            position_id: ID de la position
            exit_price: Prix de sortie
            exit_quantity: Quantité de sortie
            orders: Ordres associés

        Returns:
            Position fermée
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                raise ValueError(f"Position {position_id} non trouvée")

            if position["status"] != PositionStatus.OPEN.value:
                raise ValueError(f"Position {position_id} déjà fermée")

            entry_price = Decimal(position["entry_price"])
            quantity = Decimal(position["quantity"])
            exit_qty = exit_quantity or quantity

            if exit_qty > quantity:
                raise ValueError("Quantité de sortie supérieure à la quantité de la position")

            # Calcul du PnL réalisé
            if position["side"] == "long":
                realized_pnl = (exit_price - entry_price) * exit_qty
            else:
                realized_pnl = (entry_price - exit_price) * exit_qty

            # Mise à jour de la position
            if exit_qty == quantity:
                # Fermeture complète
                position["status"] = PositionStatus.CLOSED.value
                position["closed_at"] = datetime.now().isoformat()
                self._active_positions.remove(position_id)
                self._closed_positions.append(position_id)
                self._metrics["active_positions"] -= 1
                self._metrics["closed_positions"] += 1
            else:
                # Fermeture partielle
                position["quantity"] = str(quantity - exit_qty)
                position["status"] = PositionStatus.PARTIALLY_CLOSED.value

            position["current_price"] = str(exit_price)
            position["current_value"] = str(exit_price * Decimal(position["quantity"]))
            position["realized_pnl"] = str(Decimal(position.get("realized_pnl", "0")) + realized_pnl)
            
            # Calcul du ROI réalisé
            entry_value = entry_price * exit_qty
            position["realized_pnl_percent"] = float(realized_pnl / entry_value * 100) if entry_value > 0 else 0

            if orders:
                position["orders"].extend(orders)

            # Mise à jour des métriques
            self._metrics["total_pnl_usd"] += realized_pnl
            
            # Mise à jour du win rate
            if realized_pnl > 0:
                wins = self._metrics["win_rate"] * (self._metrics["closed_positions"] - 1) + 1
                self._metrics["win_rate"] = wins / self._metrics["closed_positions"]
            
            # Meilleur/pire trade
            if realized_pnl > self._metrics["best_trade"]:
                self._metrics["best_trade"] = realized_pnl
            if realized_pnl < self._metrics["worst_trade"]:
                self._metrics["worst_trade"] = realized_pnl

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_position(position_id)

            logger.info(f"Position {position_id} fermée: PnL = {realized_pnl}")
            return position

        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la position: {e}")
            raise

    # ========================================================================
    # GESTION DES STOPS
    # ========================================================================

    async def _check_stops(
        self,
        position_id: UUID,
        current_price: Decimal
    ) -> None:
        """
        Vérifie les stops d'une position.

        Args:
            position_id: ID de la position
            current_price: Prix actuel
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                return

            # Stop Loss
            if position.get("stop_loss"):
                stop_loss = Decimal(position["stop_loss"])
                
                if position["side"] == "long" and current_price <= stop_loss:
                    await self._trigger_stop_loss(position_id)
                elif position["side"] == "short" and current_price >= stop_loss:
                    await self._trigger_stop_loss(position_id)

            # Take Profit
            if position.get("take_profit"):
                take_profit = Decimal(position["take_profit"])
                
                if position["side"] == "long" and current_price >= take_profit:
                    await self._trigger_take_profit(position_id)
                elif position["side"] == "short" and current_price <= take_profit:
                    await self._trigger_take_profit(position_id)

            # Trailing Stop
            if position.get("trailing_stop"):
                await self._update_trailing_stop(position_id, current_price)

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des stops: {e}")

    async def _trigger_stop_loss(self, position_id: UUID) -> None:
        """
        Déclenche un stop loss.

        Args:
            position_id: ID de la position
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                return

            logger.warning(f"Stop Loss déclenché pour {position_id}")
            
            # Fermeture de la position
            current_price = Decimal(position["current_price"])
            await self.close_position(
                position_id=position_id,
                exit_price=current_price * Decimal("0.99")  # Slippage
            )

        except Exception as e:
            logger.error(f"Erreur lors du déclenchement du stop loss: {e}")

    async def _trigger_take_profit(self, position_id: UUID) -> None:
        """
        Déclenche un take profit.

        Args:
            position_id: ID de la position
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                return

            logger.info(f"Take Profit déclenché pour {position_id}")
            
            # Fermeture de la position
            current_price = Decimal(position["current_price"])
            await self.close_position(
                position_id=position_id,
                exit_price=current_price
            )

        except Exception as e:
            logger.error(f"Erreur lors du déclenchement du take profit: {e}")

    async def _update_trailing_stop(
        self,
        position_id: UUID,
        current_price: Decimal
    ) -> None:
        """
        Met à jour le trailing stop.

        Args:
            position_id: ID de la position
            current_price: Prix actuel
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                return

            trailing_stop_pct = Decimal(position["trailing_stop"])
            highest = Decimal(position["highest_price"])
            
            if position["side"] == "long" and current_price > highest:
                new_stop = current_price * (1 - trailing_stop_pct)
                position["stop_loss"] = str(new_stop)
                position["highest_price"] = str(current_price)
            
            elif position["side"] == "short" and current_price < Decimal(position["lowest_price"]):
                new_stop = current_price * (1 + trailing_stop_pct)
                position["stop_loss"] = str(new_stop)
                position["lowest_price"] = str(current_price)

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du trailing stop: {e}")

    # ========================================================================
    # GESTION DES RISQUES
    # ========================================================================

    async def _check_risk_limits(
        self,
        bot_id: UUID,
        quantity: Decimal,
        price: Decimal
    ) -> None:
        """
        Vérifie les limites de risque.

        Args:
            bot_id: ID du bot
            quantity: Quantité
            price: Prix

        Raises:
            ValueError: Si une limite est dépassée
        """
        position_value = quantity * price

        # Vérification de la taille max
        if position_value > self.risk_limits["max_position_size"]:
            raise ValueError(
                f"Taille de position {position_value} dépasse la limite {self.risk_limits['max_position_size']}"
            )

        # Vérification de l'exposition totale
        total_exposure = sum(
            Decimal(p["quantity"]) * Decimal(p["entry_price"])
            for p in self._positions.values()
            if p["status"] == PositionStatus.OPEN.value
        )
        
        if (total_exposure + position_value) / self.risk_limits["max_position_size"] > self.risk_limits["max_exposure"]:
            raise ValueError("Exposition maximale atteinte")

        # Vérification des pertes quotidiennes
        today_losses = sum(
            Decimal(p.get("realized_pnl", "0"))
            for p in self._positions.values()
            if p.get("closed_at") and datetime.fromisoformat(p["closed_at"]).date() == datetime.now().date()
            and Decimal(p.get("realized_pnl", "0")) < 0
        )
        
        if abs(today_losses) > self.risk_limits["max_daily_loss"]:
            raise ValueError("Limite de pertes quotidiennes atteinte")

    async def calculate_risk_metrics(
        self,
        position_id: UUID,
        historical_prices: Optional[List[Decimal]] = None
    ) -> RiskMetrics:
        """
        Calcule les métriques de risque d'une position.

        Args:
            position_id: ID de la position
            historical_prices: Prix historiques

        Returns:
            Métriques de risque
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                raise ValueError(f"Position {position_id} non trouvée")

            # Récupération des prix historiques
            if not historical_prices:
                historical_prices = await self._get_historical_prices(
                    position["symbol"],
                    self.VAR_HISTORICAL_DAYS
                )

            if not historical_prices or len(historical_prices) < 10:
                return self._default_risk_metrics(position_id)

            # Calcul des rendements
            returns = []
            for i in range(1, len(historical_prices)):
                if historical_prices[i-1] > 0:
                    ret = float((historical_prices[i] - historical_prices[i-1]) / historical_prices[i-1])
                    returns.append(ret)

            if not returns:
                return self._default_risk_metrics(position_id)

            # Volatilité
            volatility = np.std(returns) * np.sqrt(252)

            # Value at Risk
            var_95 = np.percentile(returns, 5)
            var_99 = np.percentile(returns, 1)

            # Expected Shortfall
            tail_returns = [r for r in returns if r < var_95]
            expected_shortfall = np.mean(tail_returns) if tail_returns else var_95

            # Drawdown
            cumulative = np.cumprod(1 + np.array(returns))
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = abs(np.min(drawdown)) * 100
            current_drawdown = abs(drawdown[-1]) * 100 if drawdown[-1] < 0 else 0

            # Sharpe Ratio
            risk_free_rate = 0.02
            avg_return = np.mean(returns)
            sharpe_ratio = (avg_return - risk_free_rate / 252) / (np.std(returns) + 0.0001) * np.sqrt(252)

            # Sortino Ratio
            downside_returns = [r for r in returns if r < 0]
            downside_deviation = np.std(downside_returns) if downside_returns else 0.0001
            sortino_ratio = (avg_return - risk_free_rate / 252) / downside_deviation * np.sqrt(252)

            # Calmar Ratio
            calmar_ratio = (avg_return * 252) / (max_drawdown / 100) if max_drawdown > 0 else 0

            # Beta et Alpha (simplifiés)
            beta = 1.0
            alpha = 0.0

            # VaR Ratio
            var_ratio = abs(var_95 / (avg_return + 0.0001))

            # Risk-Reward Ratio
            risk_reward_ratio = abs(avg_return / var_95) if var_95 != 0 else 0

            # Conversion des valeurs
            position_value = Decimal(position["quantity"]) * Decimal(position["current_price"])
            var_95_value = Decimal(str(abs(var_95))) * position_value
            var_99_value = Decimal(str(abs(var_99))) * position_value
            es_value = Decimal(str(abs(expected_shortfall))) * position_value

            return RiskMetrics(
                position_id=position_id,
                value_at_risk_95=var_95_value,
                value_at_risk_99=var_99_value,
                expected_shortfall=es_value,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                volatility=volatility * 100,
                beta=beta,
                alpha=alpha,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                var_ratio=var_ratio,
                risk_reward_ratio=risk_reward_ratio
            )

        except Exception as e:
            logger.error(f"Erreur lors du calcul des métriques de risque: {e}")
            return self._default_risk_metrics(position_id)

    def _default_risk_metrics(self, position_id: UUID) -> RiskMetrics:
        """
        Retourne des métriques de risque par défaut.

        Args:
            position_id: ID de la position

        Returns:
            Métriques de risque par défaut
        """
        return RiskMetrics(
            position_id=position_id,
            value_at_risk_95=Decimal("0"),
            value_at_risk_99=Decimal("0"),
            expected_shortfall=Decimal("0"),
            max_drawdown=0.0,
            current_drawdown=0.0,
            volatility=0.0,
            beta=1.0,
            alpha=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            var_ratio=0.0,
            risk_reward_ratio=0.0
        )

    # ========================================================================
    # CALCUL DES MÉTRIQUES
    # ========================================================================

    async def calculate_position_metrics(
        self,
        position_id: UUID
    ) -> PositionMetrics:
        """
        Calcule les métriques d'une position.

        Args:
            position_id: ID de la position

        Returns:
            Métriques de position
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                raise ValueError(f"Position {position_id} non trouvée")

            entry_price = Decimal(position["entry_price"])
            quantity = Decimal(position["quantity"])
            entry_value = entry_price * quantity

            # PnL
            total_pnl = Decimal(position.get("realized_pnl", "0")) + Decimal(position.get("unrealized_pnl", "0"))
            
            # Frais totaux
            total_fees = Decimal(position.get("total_fees", "0"))

            # Volume total
            total_volume = entry_value + Decimal(position.get("current_value", "0"))

            # ROI
            roi = float(total_pnl / entry_value * 100) if entry_value > 0 else 0

            # Holding period
            opened_at = datetime.fromisoformat(position["opened_at"])
            if position["closed_at"]:
                closed_at = datetime.fromisoformat(position["closed_at"])
                holding_period = (closed_at - opened_at).total_seconds() / 3600
            else:
                holding_period = (datetime.now() - opened_at).total_seconds() / 3600

            # Métriques de trading
            wins = len([o for o in position.get("orders", []) if Decimal(o.get("pnl", "0")) > 0])
            total_orders = len(position.get("orders", []))
            win_rate = wins / total_orders if total_orders > 0 else 0

            profit_factor = 1.0
            recovery_factor = 1.0

            # Sharpe et Sortino
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

            return PositionMetrics(
                position_id=position_id,
                total_pnl=total_pnl,
                total_pnl_usd=total_pnl * Decimal("1"),  # Conversion USD
                realized_pnl=Decimal(position.get("realized_pnl", "0")),
                unrealized_pnl=Decimal(position.get("unrealized_pnl", "0")),
                total_fees=total_fees,
                total_volume=total_volume,
                max_drawdown=await self._calculate_max_drawdown(position),
                max_profit=await self._calculate_max_profit(position),
                average_entry=entry_price,
                average_exit=Decimal(position.get("current_price", "0")),
                holding_period=holding_period,
                roi_percentage=roi,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                win_rate=win_rate,
                profit_factor=profit_factor,
                recovery_factor=recovery_factor
            )

        except Exception as e:
            logger.error(f"Erreur lors du calcul des métriques: {e}")
            raise

    async def _calculate_max_drawdown(
        self,
        position: Dict[str, Any]
    ) -> float:
        """
        Calcule le max drawdown d'une position.

        Args:
            position: Position

        Returns:
            Max drawdown
        """
        # Simuler avec les données disponibles
        return 0.05

    async def _calculate_max_profit(
        self,
        position: Dict[str, Any]
    ) -> float:
        """
        Calcule le profit maximum d'une position.

        Args:
            position: Position

        Returns:
            Profit maximum
        """
        # Simuler avec les données disponibles
        return 0.02

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_position(
        self,
        position_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère une position.

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        # Vérification du cache
        if position_id in self._positions:
            return self._positions[position_id]

        # Chargement depuis Redis
        if self.redis:
            return await self._load_position(position_id)

        return None

    async def get_positions(
        self,
        bot_id: Optional[UUID] = None,
        exchange: Optional[ExchangeType] = None,
        symbol: Optional[str] = None,
        status: Optional[PositionStatus] = None,
        position_type: Optional[PositionType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Récupère les positions.

        Args:
            bot_id: Filtrer par bot
            exchange: Filtrer par exchange
            symbol: Filtrer par symbole
            status: Filtrer par statut
            position_type: Filtrer par type
            limit: Nombre de positions
            offset: Décalage

        Returns:
            Liste des positions
        """
        positions = list(self._positions.values())
        
        if bot_id:
            positions = [p for p in positions if p["bot_id"] == str(bot_id)]
        if exchange:
            positions = [p for p in positions if p["exchange"] == exchange.value]
        if symbol:
            positions = [p for p in positions if p["symbol"] == symbol]
        if status:
            positions = [p for p in positions if p["status"] == status.value]
        if position_type:
            positions = [p for p in positions if p["type"] == position_type.value]
        
        positions.sort(key=lambda x: x["opened_at"], reverse=True)
        
        return positions[offset:offset + limit]

    async def get_active_positions(
        self,
        bot_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère les positions actives.

        Args:
            bot_id: Filtrer par bot

        Returns:
            Liste des positions actives
        """
        return await self.get_positions(
            bot_id=bot_id,
            status=PositionStatus.OPEN
        )

    # ========================================================================
    # MÉTHODES DE STOCKAGE
    # ========================================================================

    async def _save_position(self, position_id: UUID) -> None:
        """
        Sauvegarde une position dans Redis.

        Args:
            position_id: ID de la position
        """
        try:
            position = self._positions.get(position_id)
            if not position:
                return

            key = f"position:{position_id}"
            await self.redis.setex(
                key,
                86400 * 30,  # 30 jours
                json.dumps(position)
            )

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la position: {e}")

    async def _load_position(self, position_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Charge une position depuis Redis.

        Args:
            position_id: ID de la position

        Returns:
            Position chargée
        """
        try:
            key = f"position:{position_id}"
            data = await self.redis.get(key)
            if data:
                position = json.loads(data)
                self._positions[position_id] = position
                return position
            return None

        except Exception as e:
            logger.error(f"Erreur lors du chargement de la position: {e}")
            return None

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
                "total_positions": self._metrics["total_positions"],
                "active_positions": self._metrics["active_positions"],
                "closed_positions": self._metrics["closed_positions"],
                "total_pnl_usd": float(self._metrics["total_pnl_usd"]),
                "total_fees_usd": float(self._metrics["total_fees_usd"]),
                "total_volume_usd": float(self._metrics["total_volume_usd"]),
                "win_rate": self._metrics["win_rate"],
                "profit_factor": self._metrics["profit_factor"],
                "average_roi": self._metrics["average_roi"],
                "max_drawdown": self._metrics["max_drawdown"],
                "best_trade": float(self._metrics["best_trade"]),
                "worst_trade": float(self._metrics["worst_trade"]),
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
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
        logger.info("Fermeture de ArbitrageBotPositionManager...")
        self._positions.clear()
        self._metrics_cache.clear()
        self._risk_metrics_cache.clear()
        self._active_positions.clear()
        self._closed_positions.clear()
        self._price_history.clear()
        logger.info("ArbitrageBotPositionManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_arbitrage_bot_position_manager(
    redis_url: str = "redis://localhost:6379/0",
    risk_limits: Optional[Dict[str, Any]] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> ArbitrageBotPositionManager:
    """
    Crée une instance du gestionnaire de positions.

    Args:
        redis_url: URL de connexion Redis
        risk_limits: Limites de risque
        api_keys: Clés API

    Returns:
        Instance du gestionnaire
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ArbitrageBotPositionManager(
        redis_client=redis_client,
        risk_limits=risk_limits,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PositionStatus",
    "PositionType",
    "PositionMetrics",
    "RiskMetrics",
    "ArbitrageBotPositionManager",
    "create_arbitrage_bot_position_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire de positions."""
    print("=" * 60)
    print("NEXUS AI TRADING - ARBITRAGE BOT POSITION MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    position_manager = create_arbitrage_bot_position_manager(
        risk_limits={
            "max_position_size": Decimal("50000"),
            "max_exposure": 0.5,
            "max_daily_loss": Decimal("5000")
        }
    )

    # Création d'un bot exemple
    bot_id = uuid4()
    print(f"\n✅ Bot ID: {bot_id}")

    # Création d'une position
    print(f"\n📊 Création d'une position...")
    position = await position_manager.create_position(
        bot_id=bot_id,
        exchange=ExchangeType.BINANCE,
        symbol="BTC/USDT",
        position_type=PositionType.LONG,
        side="long",
        entry_price=Decimal("50000"),
        quantity=Decimal("0.1"),
        stop_loss=Decimal("48000"),
        take_profit=Decimal("55000"),
        trailing_stop=Decimal("0.02"),
        metadata={"strategy": "trend_following"}
    )

    print(f"   ID: {position['position_id']}")
    print(f"   Symbole: {position['symbol']}")
    print(f"   Type: {position['type']}")
    print(f"   Entry: ${position['entry_price']}")
    print(f"   Quantity: {position['quantity']}")

    # Mise à jour de la position
    print(f"\n🔄 Mise à jour de la position...")
    await position_manager.update_position(
        UUID(position["position_id"]),
        Decimal("52000")
    )
    
    updated = await position_manager.get_position(UUID(position["position_id"]))
    print(f"   Prix actuel: ${updated['current_price']}")
    print(f"   PnL non réalisé: ${updated['unrealized_pnl']}")

    # Calcul des métriques
    print(f"\n📈 Calcul des métriques...")
    metrics = await position_manager.calculate_position_metrics(
        UUID(position["position_id"])
    )
    print(f"   ROI: {metrics.roi_percentage:.2f}%")
    print(f"   Holding Period: {metrics.holding_period:.1f}h")

    # Calcul des métriques de risque
    print(f"\n⚠️ Calcul des métriques de risque...")
    risk_metrics = await position_manager.calculate_risk_metrics(
        UUID(position["position_id"])
    )
    print(f"   VaR 95%: ${risk_metrics.value_at_risk_95:.2f}")
    print(f"   VaR 99%: ${risk_metrics.value_at_risk_99:.2f}")
    print(f"   Volatilité: {risk_metrics.volatility:.2f}%")

    # Récupération des positions actives
    active = await position_manager.get_active_positions(bot_id)
    print(f"\n📋 Positions actives: {len(active)}")

    # Statistiques
    stats = await position_manager.get_health()
    print(f"\n📊 Statistiques:")
    print(f"   Total positions: {stats['total_positions']}")
    print(f"   PnL total: ${stats['total_pnl_usd']:.2f}")
    print(f"   Win rate: {stats['win_rate']*100:.1f}%")

    # Fermeture
    await position_manager.close()

    print("\n" + "=" * 60)
    print("ArbitrageBotPositionManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())


# blockchain/bridges/bridge_fees.py
"""
NEXUS AI TRADING SYSTEM - Bridge Fees Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BridgeFeeConfig:
    """Configuration des frais de bridge"""
    bridge_name: str
    fee_rate: float = 0.001  # 0.1%
    min_fee: float = 0.0
    max_fee: float = float('inf')
    gas_price_multiplier: float = 1.1
    base_gas_limit: int = 100000
    dynamic_fees: bool = True
    fee_update_interval: int = 3600  # secondes
    discount_rate: float = 0.0
    loyalty_discount: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bridge_name': self.bridge_name,
            'fee_rate': self.fee_rate,
            'min_fee': self.min_fee,
            'max_fee': self.max_fee,
            'gas_price_multiplier': self.gas_price_multiplier,
            'base_gas_limit': self.base_gas_limit,
            'dynamic_fees': self.dynamic_fees,
            'fee_update_interval': self.fee_update_interval,
            'discount_rate': self.discount_rate,
            'loyalty_discount': self.loyalty_discount,
        }


@dataclass
class BridgeFeeCalculation:
    """Calcul des frais de bridge"""
    bridge_name: str
    amount: float
    token: str
    base_fee: float
    gas_fee: float
    total_fee: float
    fee_rate: float
    gas_price: float
    gas_limit: int
    discount_applied: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bridge_name': self.bridge_name,
            'amount': self.amount,
            'token': self.token,
            'base_fee': self.base_fee,
            'gas_fee': self.gas_fee,
            'total_fee': self.total_fee,
            'fee_rate': self.fee_rate,
            'gas_price': self.gas_price,
            'gas_limit': self.gas_limit,
            'discount_applied': self.discount_applied,
            'timestamp': self.timestamp.isoformat(),
        }


class BridgeFeeManager:
    """
    Gestionnaire des frais de bridge.

    Features:
    - Calcul des frais
    - Frais dynamiques
    - Remises
    - Optimisation des gas
    - Historique des frais

    Example:
        ```python
        config = BridgeFeeConfig(
            bridge_name='arbitrum',
            fee_rate=0.001,
            dynamic_fees=True
        )
        manager = BridgeFeeManager(config)

        # Calcul des frais
        fee = manager.calculate_fee(1000, 'ETH')

        # Optimisation
        optimized = manager.optimize_fee(fee)
        ```
    """

    def __init__(self, config: Optional[BridgeFeeConfig] = None):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

        self.config = config or BridgeFeeConfig(bridge_name="default")
        self.w3 = Web3()
        self.fee_history: List[BridgeFeeCalculation] = []
        self.gas_price_history: List[float] = []
        self.last_update = datetime.now()

        logger.info(f"BridgeFeeManager initialisé pour {self.config.bridge_name}")

    def get_gas_price(self) -> float:
        """
        Récupère le prix du gaz actuel.

        Returns:
            float: Prix du gaz en Gwei
        """
        try:
            gas_price = self.w3.eth.gas_price / 1e9
            self.gas_price_history.append(gas_price)
            return gas_price
        except Exception as e:
            logger.error(f"Erreur récupération gas price: {e}")
            return 50.0  # Valeur par défaut

    def calculate_fee(
        self,
        amount: float,
        token: str,
        gas_limit: Optional[int] = None,
        gas_price: Optional[float] = None
    ) -> BridgeFeeCalculation:
        """
        Calcule les frais de bridge.

        Args:
            amount: Montant à bridge
            token: Symbole du token
            gas_limit: Limite de gaz (optionnel)
            gas_price: Prix du gaz (optionnel)

        Returns:
            BridgeFeeCalculation: Calcul des frais
        """
        if gas_limit is None:
            gas_limit = self.config.base_gas_limit

        if gas_price is None:
            gas_price = self.get_gas_price()

        # Frais de base
        base_fee = amount * self.config.fee_rate

        # Application des remises
        discount = self.config.discount_rate + self.config.loyalty_discount
        base_fee = base_fee * (1 - discount)

        # Frais de gaz
        gas_fee = gas_price * gas_limit * self.config.gas_price_multiplier / 1e9

        # Frais minimum et maximum
        total_fee = base_fee + gas_fee
        total_fee = max(total_fee, self.config.min_fee)
        total_fee = min(total_fee, self.config.max_fee)

        # Mise à jour dynamique
        if self.config.dynamic_fees:
            total_fee = self._apply_dynamic_adjustment(total_fee, amount)

        calculation = BridgeFeeCalculation(
            bridge_name=self.config.bridge_name,
            amount=amount,
            token=token,
            base_fee=base_fee,
            gas_fee=gas_fee,
            total_fee=total_fee,
            fee_rate=total_fee / amount if amount > 0 else 0,
            gas_price=gas_price,
            gas_limit=gas_limit,
            discount_applied=discount,
            timestamp=datetime.now(),
        )

        self.fee_history.append(calculation)

        return calculation

    def _apply_dynamic_adjustment(self, fee: float, amount: float) -> float:
        """
        Applique un ajustement dynamique des frais.

        Args:
            fee: Frais actuel
            amount: Montant

        Returns:
            float: Frais ajusté
        """
        if not self.fee_history:
            return fee

        # Analyse des frais récents
        recent_fees = [f.total_fee for f in self.fee_history[-10:]]
        avg_fee = np.mean(recent_fees) if recent_fees else fee

        # Ajustement basé sur le volume
        if amount > 10000:
            fee = fee * 0.95  # Réduction pour gros volumes
        elif amount < 100:
            fee = fee * 1.1  # Majoration pour petits volumes

        # Ajustement basé sur la congestion
        if len(self.gas_price_history) > 10:
            avg_gas = np.mean(self.gas_price_history[-10:])
            current_gas = self.gas_price_history[-1]
            if current_gas > avg_gas * 1.5:
                fee = fee * 1.2  # Majoration en période de congestion

        return fee

    def optimize_fee(
        self,
        fee: BridgeFeeCalculation,
        max_fee: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Optimise les frais de bridge.

        Args:
            fee: Calcul des frais
            max_fee: Frais maximum autorisé

        Returns:
            Dict[str, Any]: Optimisation
        """
        optimization = {
            'original_fee': fee.total_fee,
            'optimized_fee': fee.total_fee,
            'savings': 0.0,
            'suggestions': [],
        }

        # Optimisation du gas
        if fee.gas_limit > self.config.base_gas_limit:
            optimization['suggestions'].append({
                'type': 'gas_limit',
                'message': 'Réduire la limite de gaz',
                'saving': fee.gas_fee * 0.1,
            })
            optimization['optimized_fee'] -= optimization['suggestions'][-1]['saving']

        # Optimisation du moment
        current_hour = datetime.now().hour
        if 14 <= current_hour <= 18:  # Heures de pointe
            optimization['suggestions'].append({
                'type': 'timing',
                'message': 'Effectuer la transaction en dehors des heures de pointe',
                'saving': fee.gas_fee * 0.2,
            })
            optimization['optimized_fee'] -= optimization['suggestions'][-1]['saving']

        # Limitation
        if max_fee and optimization['optimized_fee'] > max_fee:
            optimization['optimized_fee'] = max_fee
            optimization['suggestions'].append({
                'type': 'cap',
                'message': f'Frais limités à {max_fee}',
                'saving': optimization['original_fee'] - max_fee,
            })

        optimization['savings'] = optimization['original_fee'] - optimization['optimized_fee']

        return optimization

    def get_fee_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques des frais.

        Returns:
            Dict[str, Any]: Statistiques
        """
        if not self.fee_history:
            return {
                'total_transactions': 0,
                'average_fee': 0.0,
                'min_fee': 0.0,
                'max_fee': 0.0,
            }

        fees = [f.total_fee for f in self.fee_history]

        return {
            'total_transactions': len(self.fee_history),
            'average_fee': np.mean(fees),
            'min_fee': np.min(fees),
            'max_fee': np.max(fees),
            'average_gas_price': np.mean(self.gas_price_history) if self.gas_price_history else 0,
            'average_gas_fee': np.mean([f.gas_fee for f in self.fee_history]),
            'average_base_fee': np.mean([f.base_fee for f in self.fee_history]),
            'fee_rate': self.config.fee_rate,
        }

    def estimate_fee_range(
        self,
        amount: float,
        token: str
    ) -> Tuple[float, float]:
        """
        Estime la plage des frais.

        Args:
            amount: Montant à bridge
            token: Symbole du token

        Returns:
            Tuple[float, float]: (Min, Max)
        """
        # Frais minimum
        min_gas_price = 10.0
        min_calc = self.calculate_fee(amount, token, gas_price=min_gas_price)

        # Frais maximum
        max_gas_price = 200.0
        max_calc = self.calculate_fee(amount, token, gas_price=max_gas_price)

        return min_calc.total_fee, max_calc.total_fee

    def reset_history(self) -> None:
        """Réinitialise l'historique des frais"""
        self.fee_history = []
        self.gas_price_history = []
        logger.info("Historique des frais réinitialisé")


def create_bridge_fee_manager(
    bridge_name: str = "default",
    fee_rate: float = 0.001,
    **kwargs
) -> BridgeFeeManager:
    """
    Factory pour créer un gestionnaire de frais de bridge.

    Args:
        bridge_name: Nom du bridge
        fee_rate: Taux de frais
        **kwargs: Arguments supplémentaires

    Returns:
        BridgeFeeManager: Gestionnaire
    """
    config = BridgeFeeConfig(
        bridge_name=bridge_name,
        fee_rate=fee_rate,
        **kwargs
    )
    return BridgeFeeManager(config)


__all__ = [
    'BridgeFeeManager',
    'BridgeFeeConfig',
    'BridgeFeeCalculation',
    'create_bridge_fee_manager',
]

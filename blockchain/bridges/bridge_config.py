
# blockchain/bridges/bridge_config.py
"""
NEXUS AI TRADING SYSTEM - Bridge Configuration Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import json
import os
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class BridgeType(Enum):
    """Types de bridges"""
    ARBITRUM = "arbitrum"
    AVALANCHE = "avalanche"
    BINANCE = "binance"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    SOLANA = "solana"
    CUSTOM = "custom"


class BridgeStatus(Enum):
    """Statuts des bridges"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    SYNCING = "syncing"


@dataclass
class BridgeEndpoint:
    """Endpoint d'un bridge"""
    name: str
    url: str
    chain_id: int
    network: str
    is_websocket: bool = False
    timeout: int = 30
    retry_count: int = 3
    rate_limit: int = 100  # requêtes par minute

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'url': self.url,
            'chain_id': self.chain_id,
            'network': self.network,
            'is_websocket': self.is_websocket,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'rate_limit': self.rate_limit,
        }


@dataclass
class BridgeToken:
    """Token supporté par un bridge"""
    symbol: str
    name: str
    address: str
    decimals: int
    chain: str
    is_native: bool = False
    min_amount: float = 0.0
    max_amount: float = float('inf')
    fee_rate: float = 0.001

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'name': self.name,
            'address': self.address,
            'decimals': self.decimals,
            'chain': self.chain,
            'is_native': self.is_native,
            'min_amount': self.min_amount,
            'max_amount': self.max_amount,
            'fee_rate': self.fee_rate,
        }


@dataclass
class BridgeConfig:
    """Configuration d'un bridge"""
    name: str
    bridge_type: BridgeType
    status: BridgeStatus = BridgeStatus.ACTIVE
    endpoints: List[BridgeEndpoint] = field(default_factory=list)
    tokens: List[BridgeToken] = field(default_factory=list)
    gas_limit: int = 1000000
    gas_price_multiplier: float = 1.1
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 300
    min_balance: float = 0.0
    max_balance: float = float('inf')
    maintenance_mode: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'bridge_type': self.bridge_type.value,
            'status': self.status.value,
            'endpoints': [e.to_dict() for e in self.endpoints],
            'tokens': [t.to_dict() for t in self.tokens],
            'gas_limit': self.gas_limit,
            'gas_price_multiplier': self.gas_price_multiplier,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
            'min_balance': self.min_balance,
            'max_balance': self.max_balance,
            'maintenance_mode': self.maintenance_mode,
            'metadata': self.metadata,
        }


class BridgeConfigManager:
    """
    Gestionnaire de configuration des bridges.

    Features:
    - Chargement/Sauvegarde des configurations
    - Gestion des endpoints
    - Gestion des tokens
    - Validation des configurations

    Example:
        ```python
        manager = BridgeConfigManager()

        # Charger la configuration
        config = manager.load_config('arbitrum')

        # Ajouter un endpoint
        manager.add_endpoint('arbitrum', BridgeEndpoint(...))

        # Ajouter un token
        manager.add_token('arbitrum', BridgeToken(...))

        # Sauvegarder
        manager.save_config('arbitrum')
        ```
    """

    def __init__(self, config_dir: str = "./bridge_configs"):
        self.config_dir = config_dir
        self.configs: Dict[str, BridgeConfig] = {}

        os.makedirs(config_dir, exist_ok=True)

        logger.info(f"BridgeConfigManager initialisé (dir: {config_dir})")

    def load_config(self, name: str) -> Optional[BridgeConfig]:
        """
        Charge une configuration.

        Args:
            name: Nom de la configuration

        Returns:
            Optional[BridgeConfig]: Configuration chargée
        """
        filepath = os.path.join(self.config_dir, f"{name}.json")

        if not os.path.exists(filepath):
            logger.warning(f"Configuration non trouvée: {name}")
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            config = self._from_dict(data)
            self.configs[name] = config

            logger.info(f"Configuration chargée: {name}")
            return config

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            return None

    def save_config(self, config: Union[BridgeConfig, str]) -> bool:
        """
        Sauvegarde une configuration.

        Args:
            config: Configuration ou nom

        Returns:
            bool: True si sauvegardée
        """
        if isinstance(config, str):
            config = self.configs.get(config)
            if config is None:
                logger.error(f"Configuration non trouvée: {config}")
                return False

        try:
            filepath = os.path.join(self.config_dir, f"{config.name}.json")
            with open(filepath, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)

            logger.info(f"Configuration sauvegardée: {config.name}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    def _from_dict(self, data: Dict[str, Any]) -> BridgeConfig:
        """Crée une configuration à partir d'un dictionnaire"""
        endpoints = []
        for ep_data in data.get('endpoints', []):
            endpoints.append(BridgeEndpoint(
                name=ep_data['name'],
                url=ep_data['url'],
                chain_id=ep_data['chain_id'],
                network=ep_data['network'],
                is_websocket=ep_data.get('is_websocket', False),
                timeout=ep_data.get('timeout', 30),
                retry_count=ep_data.get('retry_count', 3),
                rate_limit=ep_data.get('rate_limit', 100),
            ))

        tokens = []
        for token_data in data.get('tokens', []):
            tokens.append(BridgeToken(
                symbol=token_data['symbol'],
                name=token_data.get('name', token_data['symbol']),
                address=token_data['address'],
                decimals=token_data.get('decimals', 18),
                chain=token_data['chain'],
                is_native=token_data.get('is_native', False),
                min_amount=token_data.get('min_amount', 0.0),
                max_amount=token_data.get('max_amount', float('inf')),
                fee_rate=token_data.get('fee_rate', 0.001),
            ))

        return BridgeConfig(
            name=data['name'],
            bridge_type=BridgeType(data['bridge_type']),
            status=BridgeStatus(data.get('status', 'active')),
            endpoints=endpoints,
            tokens=tokens,
            gas_limit=data.get('gas_limit', 1000000),
            gas_price_multiplier=data.get('gas_price_multiplier', 1.1),
            max_retries=data.get('max_retries', 3),
            retry_delay=data.get('retry_delay', 5),
            timeout=data.get('timeout', 300),
            min_balance=data.get('min_balance', 0.0),
            max_balance=data.get('max_balance', float('inf')),
            maintenance_mode=data.get('maintenance_mode', False),
            metadata=data.get('metadata', {}),
        )

    def add_endpoint(self, config_name: str, endpoint: BridgeEndpoint) -> bool:
        """
        Ajoute un endpoint à une configuration.

        Args:
            config_name: Nom de la configuration
            endpoint: Endpoint à ajouter

        Returns:
            bool: True si ajouté
        """
        config = self.configs.get(config_name)
        if config is None:
            logger.error(f"Configuration non trouvée: {config_name}")
            return False

        config.endpoints.append(endpoint)
        logger.info(f"Endpoint ajouté à {config_name}: {endpoint.name}")
        return True

    def remove_endpoint(self, config_name: str, endpoint_name: str) -> bool:
        """
        Supprime un endpoint d'une configuration.

        Args:
            config_name: Nom de la configuration
            endpoint_name: Nom de l'endpoint

        Returns:
            bool: True si supprimé
        """
        config = self.configs.get(config_name)
        if config is None:
            logger.error(f"Configuration non trouvée: {config_name}")
            return False

        for i, ep in enumerate(config.endpoints):
            if ep.name == endpoint_name:
                config.endpoints.pop(i)
                logger.info(f"Endpoint supprimé de {config_name}: {endpoint_name}")
                return True

        logger.warning(f"Endpoint non trouvé: {endpoint_name}")
        return False

    def add_token(self, config_name: str, token: BridgeToken) -> bool:
        """
        Ajoute un token à une configuration.

        Args:
            config_name: Nom de la configuration
            token: Token à ajouter

        Returns:
            bool: True si ajouté
        """
        config = self.configs.get(config_name)
        if config is None:
            logger.error(f"Configuration non trouvée: {config_name}")
            return False

        config.tokens.append(token)
        logger.info(f"Token ajouté à {config_name}: {token.symbol}")
        return True

    def remove_token(self, config_name: str, token_symbol: str) -> bool:
        """
        Supprime un token d'une configuration.

        Args:
            config_name: Nom de la configuration
            token_symbol: Symbole du token

        Returns:
            bool: True si supprimé
        """
        config = self.configs.get(config_name)
        if config is None:
            logger.error(f"Configuration non trouvée: {config_name}")
            return False

        for i, token in enumerate(config.tokens):
            if token.symbol == token_symbol:
                config.tokens.pop(i)
                logger.info(f"Token supprimé de {config_name}: {token_symbol}")
                return True

        logger.warning(f"Token non trouvé: {token_symbol}")
        return False

    def validate_config(self, config_name: str) -> List[str]:
        """
        Valide une configuration.

        Args:
            config_name: Nom de la configuration

        Returns:
            List[str]: Liste des erreurs
        """
        config = self.configs.get(config_name)
        if config is None:
            return ["Configuration non trouvée"]

        errors = []

        # Vérification des endpoints
        if not config.endpoints:
            errors.append("Aucun endpoint défini")

        for ep in config.endpoints:
            if not ep.url:
                errors.append(f"URL manquante pour l'endpoint {ep.name}")
            if ep.chain_id <= 0:
                errors.append(f"Chain ID invalide pour l'endpoint {ep.name}")

        # Vérification des tokens
        if not config.tokens:
            errors.append("Aucun token défini")

        for token in config.tokens:
            if not token.address:
                errors.append(f"Adresse manquante pour le token {token.symbol}")
            if token.decimals <= 0:
                errors.append(f"Décimales invalides pour le token {token.symbol}")

        # Vérification des paramètres
        if config.gas_limit <= 0:
            errors.append("Gas limit invalide")
        if config.gas_price_multiplier <= 0:
            errors.append("Gas price multiplier invalide")
        if config.max_retries < 0:
            errors.append("Max retries invalide")
        if config.timeout <= 0:
            errors.append("Timeout invalide")

        return errors

    def get_active_configs(self) -> List[BridgeConfig]:
        """
        Retourne les configurations actives.

        Returns:
            List[BridgeConfig]: Configurations actives
        """
        return [c for c in self.configs.values() if c.status == BridgeStatus.ACTIVE]

    def get_config(self, name: str) -> Optional[BridgeConfig]:
        """
        Retourne une configuration.

        Args:
            name: Nom de la configuration

        Returns:
            Optional[BridgeConfig]: Configuration
        """
        return self.configs.get(name)

    def list_configs(self) -> List[str]:
        """
        Retourne la liste des configurations.

        Returns:
            List[str]: Liste des noms
        """
        return list(self.configs.keys())

    def create_default_config(self, name: str, bridge_type: BridgeType) -> BridgeConfig:
        """
        Crée une configuration par défaut.

        Args:
            name: Nom de la configuration
            bridge_type: Type de bridge

        Returns:
            BridgeConfig: Configuration créée
        """
        config = BridgeConfig(
            name=name,
            bridge_type=bridge_type,
        )

        # Endpoints par défaut
        default_endpoints = {
            BridgeType.ARBITRUM: [
                BridgeEndpoint(
                    name="arbitrum_mainnet",
                    url="https://arb1.arbitrum.io/rpc",
                    chain_id=42161,
                    network="mainnet"
                )
            ],
            BridgeType.AVALANCHE: [
                BridgeEndpoint(
                    name="avalanche_mainnet",
                    url="https://api.avax.network/ext/bc/C/rpc",
                    chain_id=43114,
                    network="mainnet"
                )
            ],
            BridgeType.BINANCE: [
                BridgeEndpoint(
                    name="bsc_mainnet",
                    url="https://bsc-dataseed.binance.org",
                    chain_id=56,
                    network="mainnet"
                )
            ],
            BridgeType.OPTIMISM: [
                BridgeEndpoint(
                    name="optimism_mainnet",
                    url="https://mainnet.optimism.io",
                    chain_id=10,
                    network="mainnet"
                )
            ],
            BridgeType.POLYGON: [
                BridgeEndpoint(
                    name="polygon_mainnet",
                    url="https://polygon-rpc.com",
                    chain_id=137,
                    network="mainnet"
                )
            ],
        }

        config.endpoints = default_endpoints.get(bridge_type, [])

        self.configs[name] = config
        logger.info(f"Configuration par défaut créée: {name}")

        return config


def create_bridge_config_manager(
    config_dir: str = "./bridge_configs"
) -> BridgeConfigManager:
    """
    Factory pour créer un gestionnaire de configuration de bridge.

    Args:
        config_dir: Répertoire des configurations

    Returns:
        BridgeConfigManager: Gestionnaire
    """
    return BridgeConfigManager(config_dir)


__all__ = [
    'BridgeConfigManager',
    'BridgeConfig',
    'BridgeConfig',
    'BridgeEndpoint',
    'BridgeToken',
    'BridgeType',
    'BridgeStatus',
    'create_bridge_config_manager',
]

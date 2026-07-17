# blockchain/onchain-analysis/analysis_config.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Analysis Config - Configuration de l'Analyse On-Chain

Ce module gère la configuration centralisée de l'analyse on-chain,
incluant les paramètres d'analyse, les seuils, les métriques,
et les configurations de monitoring.

Fonctionnalités principales:
- Configuration des analyses on-chain
- Gestion des seuils et alertes
- Configuration des métriques
- Gestion des périodes d'analyse
- Support multi-protocoles
- Validation des configurations
- Mise à jour dynamique
"""

import json
import logging
import os
import yaml
import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from pathlib import Path
from collections import defaultdict
from functools import lru_cache

# Import des modules internes
try:
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.logging import get_logger
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class AnalysisEnvironment(Enum):
    """Environnements d'analyse"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class AnalysisType(Enum):
    """Types d'analyse"""
    WHALE = "whale"
    VOLUME = "volume"
    PRICE = "price"
    SENTIMENT = "sentiment"
    NETWORK = "network"
    LIQUIDITY = "liquidity"
    RISK = "risk"
    ARBITRAGE = "arbitrage"
    CUSTOM = "custom"


class MetricType(Enum):
    """Types de métriques on-chain"""
    # Whale metrics
    WHALE_TRANSACTIONS = "whale_transactions"
    WHALE_ACCUMULATION = "whale_accumulation"
    WHALE_DISTRIBUTION = "whale_distribution"
    WHALE_CONCENTRATION = "whale_concentration"
    
    # Volume metrics
    VOLUME_24H = "volume_24h"
    VOLUME_7D = "volume_7d"
    VOLUME_30D = "volume_30d"
    VOLUME_CHANGE = "volume_change"
    
    # Price metrics
    PRICE_ACTION = "price_action"
    PRICE_VOLATILITY = "price_volatility"
    PRICE_CORRELATION = "price_correlation"
    
    # Network metrics
    ACTIVE_ADDRESSES = "active_addresses"
    NEW_ADDRESSES = "new_addresses"
    TRANSACTION_COUNT = "transaction_count"
    GAS_USAGE = "gas_usage"
    NETWORK_GROWTH = "network_growth"
    
    # Liquidity metrics
    LIQUIDITY_24H = "liquidity_24h"
    LIQUIDITY_7D = "liquidity_7d"
    LIQUIDITY_RATIO = "liquidity_ratio"
    
    # Risk metrics
    RISK_SCORE = "risk_score"
    VOLATILITY_RISK = "volatility_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    COUNTERPARTY_RISK = "counterparty_risk"


@dataclass
class MetricConfig:
    """Configuration d'une métrique"""
    metric_type: MetricType
    name: str
    description: str
    unit: str
    aggregation: str  # sum, avg, max, min, count
    window: int  # secondes
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "metric_type": self.metric_type.value,
            "name": self.name,
            "description": self.description,
            "unit": self.unit,
            "aggregation": self.aggregation,
            "window": self.window,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class AnalysisConfig:
    """Configuration d'une analyse"""
    analysis_id: str
    analysis_type: AnalysisType
    name: str
    description: str
    chain: str
    tokens: List[str]
    metrics: List[MetricConfig]
    timeframe: int  # secondes
    frequency: int  # secondes
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "analysis_id": self.analysis_id,
            "analysis_type": self.analysis_type.value,
            "name": self.name,
            "description": self.description,
            "chain": self.chain,
            "tokens": self.tokens,
            "metrics": [m.to_dict() for m in self.metrics],
            "timeframe": self.timeframe,
            "frequency": self.frequency,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class AlertRule:
    """Règle d'alerte"""
    rule_id: str
    metric_type: MetricType
    condition: str  # gt, lt, gte, lte, eq, neq
    threshold: float
    severity: str  # info, warning, critical, emergency
    cooldown: int  # secondes
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "rule_id": self.rule_id,
            "metric_type": self.metric_type.value,
            "condition": self.condition,
            "threshold": self.threshold,
            "severity": self.severity,
            "cooldown": self.cooldown,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class AnalysisGlobalConfig:
    """Configuration globale d'analyse"""
    version: str
    environment: AnalysisEnvironment
    chains: List[str]
    tokens: Dict[str, List[str]]
    analyses: Dict[str, AnalysisConfig]
    alert_rules: Dict[str, AlertRule]
    default_timeframe: int = 86400  # 24 heures
    default_frequency: int = 3600  # 1 heure
    max_analyses: int = 100
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "version": self.version,
            "environment": self.environment.value,
            "chains": self.chains,
            "tokens": self.tokens,
            "analyses": {k: v.to_dict() for k, v in self.analyses.items()},
            "alert_rules": {k: v.to_dict() for k, v in self.alert_rules.items()},
            "default_timeframe": self.default_timeframe,
            "default_frequency": self.default_frequency,
            "max_analyses": self.max_analyses,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CONFIGURATIONS PAR DÉFAUT
# ============================================================

DEFAULT_METRICS = {
    MetricType.WHALE_TRANSACTIONS: {
        "name": "Whale Transactions",
        "description": "Number of large transactions (> $100k)",
        "unit": "count",
        "aggregation": "sum",
        "window": 3600,
        "threshold_warning": 10,
        "threshold_critical": 50,
    },
    MetricType.VOLUME_24H: {
        "name": "24h Volume",
        "description": "Trading volume in the last 24 hours",
        "unit": "USD",
        "aggregation": "sum",
        "window": 86400,
    },
    MetricType.PRICE_VOLATILITY: {
        "name": "Price Volatility",
        "description": "Standard deviation of price changes",
        "unit": "percent",
        "aggregation": "avg",
        "window": 3600,
        "threshold_warning": 0.05,
        "threshold_critical": 0.10,
    },
    MetricType.ACTIVE_ADDRESSES: {
        "name": "Active Addresses",
        "description": "Number of unique active addresses",
        "unit": "count",
        "aggregation": "sum",
        "window": 86400,
    },
    MetricType.NETWORK_GROWTH: {
        "name": "Network Growth",
        "description": "Growth rate of network participants",
        "unit": "percent",
        "aggregation": "avg",
        "window": 86400,
    },
    MetricType.LIQUIDITY_24H: {
        "name": "24h Liquidity",
        "description": "Liquidity available in the last 24 hours",
        "unit": "USD",
        "aggregation": "sum",
        "window": 86400,
    },
    MetricType.RISK_SCORE: {
        "name": "Risk Score",
        "description": "Overall risk score (0-100)",
        "unit": "score",
        "aggregation": "avg",
        "window": 3600,
        "threshold_warning": 70,
        "threshold_critical": 85,
    },
}

DEFAULT_ANALYSES = {
    "whale_analysis": {
        "analysis_type": "whale",
        "name": "Whale Activity Analysis",
        "description": "Analysis of whale transactions and holdings",
        "chain": "ethereum",
        "tokens": ["ETH", "USDC", "USDT"],
        "metrics": ["whale_transactions", "whale_accumulation", "whale_distribution"],
        "timeframe": 86400,
        "frequency": 3600,
        "priority": 10,
    },
    "volume_analysis": {
        "analysis_type": "volume",
        "name": "Volume Analysis",
        "description": "Analysis of trading volumes",
        "chain": "ethereum",
        "tokens": ["ETH", "USDC", "USDT"],
        "metrics": ["volume_24h", "volume_7d", "volume_30d"],
        "timeframe": 86400,
        "frequency": 3600,
        "priority": 20,
    },
    "risk_analysis": {
        "analysis_type": "risk",
        "name": "Risk Analysis",
        "description": "Analysis of various risk metrics",
        "chain": "ethereum",
        "tokens": ["ETH", "USDC", "USDT"],
        "metrics": ["risk_score", "volatility_risk", "liquidity_risk"],
        "timeframe": 86400,
        "frequency": 3600,
        "priority": 30,
    },
}

DEFAULT_ALERT_RULES = {
    "whale_alert_high": {
        "metric_type": "whale_transactions",
        "condition": "gt",
        "threshold": 50,
        "severity": "critical",
        "cooldown": 3600,
    },
    "volume_alert_drop": {
        "metric_type": "volume_24h",
        "condition": "lt",
        "threshold": 1000000,
        "severity": "warning",
        "cooldown": 7200,
    },
    "risk_alert_high": {
        "metric_type": "risk_score",
        "condition": "gt",
        "threshold": 85,
        "severity": "critical",
        "cooldown": 3600,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class AnalysisConfigManager:
    """
    Gestionnaire de configuration de l'analyse on-chain
    """

    def __init__(
        self,
        config_dir: Optional[str] = None,
        environment: AnalysisEnvironment = AnalysisEnvironment.PRODUCTION,
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de configuration

        Args:
            config_dir: Répertoire des configurations
            environment: Environnement
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(__file__), "configs"
        )
        self.environment = environment
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # Configuration
        self._config: Optional[AnalysisGlobalConfig] = None
        self._config_cache: Dict[str, Tuple[float, Any]] = {}

        # Création du répertoire
        os.makedirs(self.config_dir, exist_ok=True)

        # Chargement de la configuration
        self._load_config()

        logger.info(f"AnalysisConfigManager initialisé (environnement: {environment.value})")

    # ============================================================
    # MÉTHODES DE CHARGEMENT
    # ============================================================

    def _load_config(self) -> None:
        """Charge la configuration complète"""
        try:
            # Chargement des configurations
            analyses = self._load_analyses()
            alert_rules = self._load_alert_rules()
            tokens = self._load_tokens()
            chains = self._load_chains()

            # Création de la configuration
            self._config = AnalysisGlobalConfig(
                version="1.0.0",
                environment=self.environment,
                chains=chains,
                tokens=tokens,
                analyses=analyses,
                alert_rules=alert_rules,
                default_timeframe=self.config.get("default_timeframe", 86400),
                default_frequency=self.config.get("default_frequency", 3600),
                max_analyses=self.config.get("max_analyses", 100),
                updated_at=datetime.now(),
                metadata={},
            )

            # Validation
            self._validate_config()

            logger.info(
                f"Configuration d'analyse chargée: "
                f"{len(analyses)} analyses, "
                f"{len(alert_rules)} alertes"
            )

        except Exception as e:
            logger.error(f"Erreur de chargement de la configuration: {e}")
            # Utiliser la configuration par défaut
            self._config = self._create_default_config()
            raise ConfigError(f"Erreur de chargement de la configuration: {e}")

    def _load_analyses(self) -> Dict[str, AnalysisConfig]:
        """Charge les configurations des analyses"""
        analyses = {}

        # Chargement depuis les fichiers
        analyses_dir = os.path.join(self.config_dir, "analyses")
        if os.path.exists(analyses_dir):
            for file in os.listdir(analyses_dir):
                if file.endswith((".yaml", ".yml")):
                    analysis_data = self._load_yaml_file(os.path.join(analyses_dir, file))
                    if analysis_data and "analysis_id" in analysis_data:
                        analysis_id = analysis_data["analysis_id"]
                        analyses[analysis_id] = self._create_analysis_config(analysis_data)

        # Ajout des analyses par défaut
        for analysis_id, default_data in DEFAULT_ANALYSES.items():
            if analysis_id not in analyses:
                analyses[analysis_id] = self._create_analysis_config({
                    "analysis_id": analysis_id,
                    **default_data,
                })

        return analyses

    def _load_alert_rules(self) -> Dict[str, AlertRule]:
        """Charge les règles d'alertes"""
        alert_rules = {}

        # Chargement depuis les fichiers
        alerts_dir = os.path.join(self.config_dir, "alerts")
        if os.path.exists(alerts_dir):
            for file in os.listdir(alerts_dir):
                if file.endswith((".yaml", ".yml")):
                    alert_data = self._load_yaml_file(os.path.join(alerts_dir, file))
                    if alert_data and "rule_id" in alert_data:
                        rule_id = alert_data["rule_id"]
                        alert_rules[rule_id] = self._create_alert_rule(alert_data)

        # Ajout des règles par défaut
        for rule_id, default_data in DEFAULT_ALERT_RULES.items():
            if rule_id not in alert_rules:
                alert_rules[rule_id] = self._create_alert_rule({
                    "rule_id": rule_id,
                    **default_data,
                })

        return alert_rules

    def _load_tokens(self) -> Dict[str, List[str]]:
        """Charge les tokens par chaîne"""
        tokens = {}

        # Chargement depuis les fichiers
        tokens_path = os.path.join(self.config_dir, "tokens.yaml")
        if os.path.exists(tokens_path):
            token_data = self._load_yaml_file(tokens_path)
            if token_data:
                for chain, chain_tokens in token_data.items():
                    tokens[chain] = chain_tokens

        # Tokens par défaut
        if not tokens:
            tokens = {
                "ethereum": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
                "bsc": ["BNB", "USDC", "USDT", "BUSD"],
                "polygon": ["MATIC", "USDC", "USDT", "DAI"],
                "arbitrum": ["ETH", "USDC", "USDT"],
                "solana": ["SOL", "USDC", "USDT"],
            }

        return tokens

    def _load_chains(self) -> List[str]:
        """Charge les chaînes supportées"""
        chains = []

        # Chargement depuis les fichiers
        chains_path = os.path.join(self.config_dir, "chains.yaml")
        if os.path.exists(chains_path):
            chain_data = self._load_yaml_file(chains_path)
            if chain_data:
                chains = chain_data.get("chains", [])

        # Chaînes par défaut
        if not chains:
            chains = ["ethereum", "bsc", "polygon", "arbitrum", "solana"]

        return chains

    def _load_yaml_file(self, path: str) -> Dict[str, Any]:
        """Charge un fichier YAML"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Erreur de chargement de {path}: {e}")
            return {}

    # ============================================================
    # MÉTHODES DE CRÉATION
    # ============================================================

    def _create_analysis_config(self, data: Dict[str, Any]) -> AnalysisConfig:
        """Crée une configuration d'analyse"""
        # Récupération des métriques
        metrics = []
        metric_names = data.get("metrics", [])
        for metric_name in metric_names:
            try:
                metric_type = MetricType(metric_name)
                if metric_type in DEFAULT_METRICS:
                    metric_data = DEFAULT_METRICS[metric_type]
                    metrics.append(MetricConfig(
                        metric_type=metric_type,
                        name=metric_data.get("name", metric_name),
                        description=metric_data.get("description", ""),
                        unit=metric_data.get("unit", ""),
                        aggregation=metric_data.get("aggregation", "sum"),
                        window=metric_data.get("window", 3600),
                        threshold_warning=metric_data.get("threshold_warning"),
                        threshold_critical=metric_data.get("threshold_critical"),
                        metadata=metric_data.get("metadata", {}),
                    ))
            except ValueError:
                logger.warning(f"Métrique inconnue: {metric_name}")

        return AnalysisConfig(
            analysis_id=data.get("analysis_id", f"analysis_{uuid.uuid4().hex[:8]}"),
            analysis_type=AnalysisType(data.get("analysis_type", "custom")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            chain=data.get("chain", "ethereum"),
            tokens=data.get("tokens", []),
            metrics=metrics,
            timeframe=data.get("timeframe", 86400),
            frequency=data.get("frequency", 3600),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
        )

    def _create_alert_rule(self, data: Dict[str, Any]) -> AlertRule:
        """Crée une règle d'alerte"""
        return AlertRule(
            rule_id=data.get("rule_id", f"rule_{uuid.uuid4().hex[:8]}"),
            metric_type=MetricType(data.get("metric_type", "volume_24h")),
            condition=data.get("condition", "gt"),
            threshold=data.get("threshold", 0),
            severity=data.get("severity", "warning"),
            cooldown=data.get("cooldown", 3600),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )

    def _create_default_config(self) -> AnalysisGlobalConfig:
        """Crée une configuration par défaut"""
        analyses = {}
        for analysis_id, default_data in DEFAULT_ANALYSES.items():
            analyses[analysis_id] = self._create_analysis_config({
                "analysis_id": analysis_id,
                **default_data,
            })

        alert_rules = {}
        for rule_id, default_data in DEFAULT_ALERT_RULES.items():
            alert_rules[rule_id] = self._create_alert_rule({
                "rule_id": rule_id,
                **default_data,
            })

        return AnalysisGlobalConfig(
            version="1.0.0",
            environment=self.environment,
            chains=["ethereum", "bsc", "polygon"],
            tokens={
                "ethereum": ["ETH", "USDC", "USDT", "DAI"],
                "bsc": ["BNB", "USDC", "USDT"],
                "polygon": ["MATIC", "USDC", "USDT"],
            },
            analyses=analyses,
            alert_rules=alert_rules,
            default_timeframe=86400,
            default_frequency=3600,
            max_analyses=100,
            updated_at=datetime.now(),
            metadata={},
        )

    # ============================================================
    # MÉTHODES DE VALIDATION
    # ============================================================

    def _validate_config(self) -> None:
        """Valide la configuration"""
        if not self._config:
            raise ConfigError("Configuration non chargée")

        # Validation des analyses
        for analysis_id, analysis in self._config.analyses.items():
            if not analysis.chain:
                raise ConfigError(f"Chaîne manquante pour l'analyse {analysis_id}")

            if not analysis.tokens:
                raise ConfigError(f"Tokens manquants pour l'analyse {analysis_id}")

            if analysis.timeframe <= 0:
                raise ConfigError(f"Timeframe invalide pour {analysis_id}")

            if analysis.frequency <= 0:
                raise ConfigError(f"Fréquence invalide pour {analysis_id}")

        # Validation des alertes
        for rule_id, rule in self._config.alert_rules.items():
            if rule.threshold < 0:
                raise ConfigError(f"Seuil invalide pour {rule_id}")

            if rule.cooldown <= 0:
                raise ConfigError(f"Cooldown invalide pour {rule_id}")

        logger.info("Configuration validée avec succès")

    # ============================================================
    # MÉTHODES D'ACCÈS
    # ============================================================

    def get_config(self) -> AnalysisGlobalConfig:
        """Obtient la configuration complète"""
        if not self._config:
            self._load_config()
        return self._config

    def get_analysis(self, analysis_id: str) -> Optional[AnalysisConfig]:
        """Obtient une configuration d'analyse"""
        return self._config.analyses.get(analysis_id)

    def get_analyses_by_type(self, analysis_type: AnalysisType) -> List[AnalysisConfig]:
        """Obtient les analyses par type"""
        return [
            a for a in self._config.analyses.values()
            if a.analysis_type == analysis_type
        ]

    def get_analyses_by_chain(self, chain: str) -> List[AnalysisConfig]:
        """Obtient les analyses par chaîne"""
        return [
            a for a in self._config.analyses.values()
            if a.chain == chain
        ]

    def get_alert_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Obtient une règle d'alerte"""
        return self._config.alert_rules.get(rule_id)

    def get_alert_rules_by_metric(self, metric_type: MetricType) -> List[AlertRule]:
        """Obtient les règles d'alerte pour une métrique"""
        return [
            r for r in self._config.alert_rules.values()
            if r.metric_type == metric_type
        ]

    def get_tokens(self, chain: Optional[str] = None) -> List[str]:
        """Obtient les tokens par chaîne"""
        if chain:
            return self._config.tokens.get(chain, [])
        return list(set(
            token for tokens in self._config.tokens.values()
            for token in tokens
        ))

    def get_chains(self) -> List[str]:
        """Obtient les chaînes supportées"""
        return self._config.chains

    def get_metric_config(self, metric_type: MetricType) -> Optional[MetricConfig]:
        """Obtient la configuration d'une métrique"""
        # Recherche dans les analyses
        for analysis in self._config.analyses.values():
            for metric in analysis.metrics:
                if metric.metric_type == metric_type:
                    return metric
        return None

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    def update_config(self, new_config: AnalysisGlobalConfig) -> None:
        """Met à jour la configuration"""
        self._config = new_config
        self._validate_config()
        self._config.updated_at = datetime.now()
        self._config_cache.clear()
        logger.info("Configuration d'analyse mise à jour")

    def reload_config(self) -> None:
        """Recharge la configuration"""
        self._load_config()
        logger.info("Configuration d'analyse rechargée")

    def save_config(self, path: Optional[str] = None) -> None:
        """Sauvegarde la configuration"""
        if not self._config:
            return

        save_path = path or os.path.join(self.config_dir, "analysis_config.yaml")

        try:
            with open(save_path, 'w') as f:
                yaml.dump(self._config.to_dict(), f, default_flow_style=False)
            logger.info(f"Configuration d'analyse sauvegardée: {save_path}")
        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            raise ConfigError(f"Erreur de sauvegarde: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de configuration"""
        if not self._config:
            return {}

        return {
            "analyses": len(self._config.analyses),
            "alert_rules": len(self._config.alert_rules),
            "chains": len(self._config.chains),
            "tokens": len(self._config.tokens),
            "enabled_analyses": len([a for a in self._config.analyses.values() if a.enabled]),
            "environment": self.environment.value,
            "version": self._config.version,
            "updated_at": self._config.updated_at.isoformat(),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources AnalysisConfigManager...")
        self._config_cache.clear()
        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_analysis_config_manager(
    config_dir: Optional[str] = None,
    environment: str = "production",
    **kwargs,
) -> AnalysisConfigManager:
    """
    Crée une instance de AnalysisConfigManager

    Args:
        config_dir: Répertoire des configurations
        environment: Environnement
        **kwargs: Arguments additionnels

    Returns:
        Instance de AnalysisConfigManager
    """
    env = AnalysisEnvironment(environment.lower())
    return AnalysisConfigManager(
        config_dir=config_dir,
        environment=env,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de AnalysisConfigManager"""
    # Création du gestionnaire
    config_manager = create_analysis_config_manager(
        config_dir="./analysis_configs",
        environment="production",
    )

    # Obtention de la configuration
    config = config_manager.get_config()
    print(f"Version: {config.version}")
    print(f"Environnement: {config.environment.value}")

    # Obtention d'une analyse
    analysis = config_manager.get_analysis("whale_analysis")
    if analysis:
        print(f"\nAnalyse Whale:")
        print(f"  Nom: {analysis.name}")
        print(f"  Chaîne: {analysis.chain}")
        print(f"  Tokens: {analysis.tokens}")
        print(f"  Métriques: {[m.name for m in analysis.metrics]}")

    # Obtention des analyses par type
    whale_analyses = config_manager.get_analyses_by_type(AnalysisType.WHALE)
    print(f"\nAnalyses Whale: {len(whale_analyses)}")

    # Obtention des tokens
    tokens = config_manager.get_tokens("ethereum")
    print(f"\nTokens sur Ethereum: {tokens}")

    # Règles d'alerte
    rules = config_manager.get_alert_rules_by_metric(MetricType.WHALE_TRANSACTIONS)
    print(f"\nRègles d'alerte pour les transactions whale: {len(rules)}")

    # Statistiques
    stats = config_manager.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Sauvegarde
    config_manager.save_config()

    # Nettoyage
    await config_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

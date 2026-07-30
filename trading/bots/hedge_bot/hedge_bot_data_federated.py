# trading/bots/hedge_bot/hedge_bot_data_federated.py
# Advanced Federated Learning & Distributed Intelligence for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Federated Data Module - Module d'apprentissage fédéré et d'intelligence distribuée avancé
pour le Hedge Bot. Permet l'apprentissage collaboratif sans partage de données sensibles,
l'agrégation de modèles distribués et l'intelligence collective pour l'optimisation du hedging.
"""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import pickle
import zlib
import copy

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_federated")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager, DataConsistency
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext, DataClass, EncryptionFactory
)


# ============== ENUMS & TYPES ==============

class FederatedRole(Enum):
    """Rôles dans le système fédéré."""
    COORDINATOR = "coordinator"
    CLIENT = "client"
    AGGREGATOR = "aggregator"
    VALIDATOR = "validator"
    OBSERVER = "observer"


class FederatedStatus(Enum):
    """Statuts du système fédéré."""
    INITIALIZED = "initialized"
    TRAINING = "training"
    AGGREGATING = "aggregating"
    VALIDATING = "validating"
    DEPLOYED = "deployed"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class AggregationMethod(Enum):
    """Méthodes d'agrégation fédérée."""
    FED_AVG = "fed_avg"
    FED_PROX = "fed_prox"
    FED_OPT = "fed_opt"
    FED_BN = "fed_bn"
    FED_MA = "fed_ma"
    FED_NOVA = "fed_nova"
    SCAFFOLD = "scaffold"
    MOON = "moon"
    PERFED = "perfed"
    FED_DYN = "fed_dyn"


class PrivacyMethod(Enum):
    """Méthodes de préservation de la vie privée."""
    DIFFERENTIAL_PRIVACY = "differential_privacy"
    HOMOMORPHIC_ENCRYPTION = "homomorphic_encryption"
    SECURE_AGGREGATION = "secure_aggregation"
    ZERO_KNOWLEDGE = "zero_knowledge"
    FEDERATED_DROPOUT = "federated_dropout"


# ============== DATA MODELS ==============

@dataclass
class FederatedNode:
    """Nœud fédéré."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: FederatedRole = FederatedRole.CLIENT
    name: str = ""
    endpoint: str = ""
    public_key: Optional[str] = None
    status: FederatedStatus = FederatedStatus.INITIALIZED
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    capabilities: List[str] = field(default_factory=list)
    data_stats: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    weight: float = 1.0
    participation_count: int = 0
    reliability_score: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "role": self.role.value,
            "name": self.name,
            "endpoint": self.endpoint,
            "public_key": self.public_key,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "capabilities": self.capabilities,
            "data_stats": self.data_stats,
            "metadata": self.metadata,
            "tags": self.tags,
            "weight": self.weight,
            "participation_count": self.participation_count,
            "reliability_score": self.reliability_score
        }


@dataclass
class FederatedModel:
    """Modèle fédéré."""
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    global_model: Any = None
    local_models: Dict[str, Any] = field(default_factory=dict)
    aggregation_method: AggregationMethod = AggregationMethod.FED_AVG
    privacy_method: Optional[PrivacyMethod] = None
    privacy_epsilon: float = 0.1
    privacy_delta: float = 1e-5
    round: int = 0
    accuracy: float = 0.0
    loss: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    status: FederatedStatus = FederatedStatus.INITIALIZED
    
    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "aggregation_method": self.aggregation_method.value,
            "privacy_method": self.privacy_method.value if self.privacy_method else None,
            "privacy_epsilon": self.privacy_epsilon,
            "privacy_delta": self.privacy_delta,
            "round": self.round,
            "accuracy": self.accuracy,
            "loss": self.loss,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "status": self.status.value,
            "node_count": len(self.local_models)
        }


@dataclass
class FederatedRound:
    """Round d'entraînement fédéré."""
    round_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    round_number: int = 0
    participants: List[str] = field(default_factory=list)
    aggregator_id: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    global_metrics: Dict[str, float] = field(default_factory=dict)
    local_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    status: FederatedStatus = FederatedStatus.TRAINING
    convergence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "round_id": self.round_id,
            "model_id": self.model_id,
            "round_number": self.round_number,
            "participants": self.participants,
            "aggregator_id": self.aggregator_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "global_metrics": self.global_metrics,
            "local_metrics": self.local_metrics,
            "status": self.status.value,
            "convergence": self.convergence,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class FederatedUpdate:
    """Mise à jour fédérée."""
    update_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    node_id: str = ""
    round_number: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    signature: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "update_id": self.update_id,
            "model_id": self.model_id,
            "node_id": self.node_id,
            "round_number": self.round_number,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "signature": self.signature,
            "timestamp": self.timestamp.isoformat(),
            "weight": self.weight,
            "metadata": self.metadata
        }


# ============== INTERFACES ==============

class FederatedEngineInterface(ABC):
    """Interface abstraite pour le moteur fédéré."""
    
    @abstractmethod
    async def register_node(self, node: FederatedNode) -> bool:
        """Enregistre un nœud fédéré."""
        pass
    
    @abstractmethod
    async def create_model(self, config: Dict[str, Any]) -> FederatedModel:
        """Crée un modèle fédéré."""
        pass
    
    @abstractmethod
    async def train_round(self, model_id: str) -> FederatedRound:
        """Exécute un round d'entraînement."""
        pass
    
    @abstractmethod
    async def aggregate(self, model_id: str, updates: List[FederatedUpdate]) -> Dict[str, Any]:
        """Agrège les mises à jour."""
        pass


# ============== IMPLÉMENTATION ==============

class FederatedEngine(FederatedEngineInterface):
    """
    Moteur d'apprentissage fédéré avancé pour le Hedge Bot.
    Permet l'entraînement distribué de modèles sans partage de données sensibles.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des nœuds
        self._nodes: Dict[str, FederatedNode] = {}
        self._nodes_lock = threading.RLock()
        
        # Gestion des modèles
        self._models: Dict[str, FederatedModel] = {}
        self._models_lock = threading.RLock()
        
        # Gestion des rounds
        self._rounds: Dict[str, FederatedRound] = {}
        self._rounds_lock = threading.RLock()
        
        # Gestion des mises à jour
        self._updates: Dict[str, List[FederatedUpdate]] = defaultdict(list)
        self._updates_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "nodes_registered": 0,
            "models_created": 0,
            "rounds_completed": 0,
            "total_participations": 0,
            "avg_accuracy": 0.0,
            "avg_loss": 0.0,
            "convergence_count": 0
        }
        
        # État
        self._is_running = False
        self._coordinator_id = str(uuid.uuid4())
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        logger.info("FederatedEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "round_timeout": 300,  # 5 minutes
            "min_participants": 2,
            "max_participants": 100,
            "aggregation_interval": 60,  # 1 minute
            "convergence_threshold": 0.001,
            "max_rounds": 100,
            "privacy": {
                "default_method": PrivacyMethod.DIFFERENTIAL_PRIVACY,
                "epsilon": 0.1,
                "delta": 1e-5,
                "clip_norm": 1.0
            },
            "aggregation": {
                "default_method": AggregationMethod.FED_AVG,
                "client_weights": "uniform",  # uniform, data_size, performance
                "secure_aggregation": True
            },
            "model": {
                "default_lr": 0.01,
                "default_batch_size": 32,
                "local_epochs": 5
            }
        }
    
    async def start(self) -> None:
        """Démarre le moteur fédéré."""
        logger.info("FederatedEngine starting...")
        self._is_running = True
        
        # Enregistrement du coordinateur
        coordinator = FederatedNode(
            node_id=self._coordinator_id,
            role=FederatedRole.COORDINATOR,
            name="Federated Coordinator",
            status=FederatedStatus.INITIALIZED,
            capabilities=["coordinate", "aggregate", "validate"]
        )
        await self.register_node(coordinator)
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._update_monitor_loop())
        asyncio.create_task(self._performance_analyzer_loop())
        
        logger.info("FederatedEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur fédéré."""
        logger.info("FederatedEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("FederatedEngine stopped")
    
    async def register_node(self, node: FederatedNode) -> bool:
        """Enregistre un nœud fédéré."""
        with self._nodes_lock:
            self._nodes[node.node_id] = node
            self._stats["nodes_registered"] += 1
        
        logger.info(f"Node registered: {node.node_id} (role={node.role.value})")
        return True
    
    async def unregister_node(self, node_id: str) -> bool:
        """Désenregistre un nœud fédéré."""
        with self._nodes_lock:
            if node_id not in self._nodes:
                return False
            del self._nodes[node_id]
        
        logger.info(f"Node unregistered: {node_id}")
        return True
    
    async def get_node(self, node_id: str) -> Optional[FederatedNode]:
        """Récupère un nœud."""
        with self._nodes_lock:
            return self._nodes.get(node_id)
    
    async def get_nodes(self, role: Optional[FederatedRole] = None) -> List[FederatedNode]:
        """Récupère les nœuds."""
        with self._nodes_lock:
            nodes = list(self._nodes.values())
            if role:
                nodes = [n for n in nodes if n.role == role]
            return nodes
    
    async def create_model(self, config: Dict[str, Any]) -> FederatedModel:
        """Crée un modèle fédéré."""
        model = FederatedModel(
            name=config.get("name", f"Model_{uuid.uuid4().hex[:8]}"),
            aggregation_method=config.get("aggregation_method", self.config["aggregation"]["default_method"]),
            privacy_method=config.get("privacy_method", self.config["privacy"]["default_method"]),
            privacy_epsilon=config.get("privacy_epsilon", self.config["privacy"]["epsilon"]),
            privacy_delta=config.get("privacy_delta", self.config["privacy"]["delta"]),
            metadata=config.get("metadata", {})
        )
        
        # Initialisation du modèle global
        model.global_model = await self._initialize_model(config)
        
        with self._models_lock:
            self._models[model.model_id] = model
            self._stats["models_created"] += 1
        
        logger.info(f"Federated model created: {model.model_id} ({model.name})")
        return model
    
    async def train_round(self, model_id: str) -> FederatedRound:
        """Exécute un round d'entraînement."""
        with self._models_lock:
            model = self._models.get(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            if model.status == FederatedStatus.STOPPED:
                raise ValueError(f"Model {model_id} is stopped")
        
        # Sélection des participants
        participants = await self._select_participants(model)
        if len(participants) < self.config["min_participants"]:
            raise ValueError(f"Not enough participants: {len(participants)}")
        
        # Création du round
        round_obj = FederatedRound(
            model_id=model_id,
            round_number=model.round + 1,
            participants=[p.node_id for p in participants],
            aggregator_id=self._coordinator_id,
            status=FederatedStatus.TRAINING
        )
        
        with self._rounds_lock:
            self._rounds[round_obj.round_id] = round_obj
        
        try:
            # Distribution du modèle aux participants
            local_updates = []
            
            for participant in participants:
                # Entraînement local
                update = await self._train_locally(model, participant, round_obj.round_number)
                if update:
                    local_updates.append(update)
                    self._stats["total_participations"] += 1
            
            # Agrégation
            if local_updates:
                aggregated = await self.aggregate(model_id, local_updates)
                
                # Mise à jour du modèle global
                model.global_model = aggregated["model"]
                model.round = round_obj.round_number
                model.accuracy = aggregated.get("accuracy", model.accuracy)
                model.loss = aggregated.get("loss", model.loss)
                model.updated_at = datetime.now(timezone.utc)
                
                # Mise à jour du round
                round_obj.status = FederatedStatus.COMPLETED
                round_obj.end_time = datetime.now(timezone.utc)
                round_obj.global_metrics = {
                    "accuracy": model.accuracy,
                    "loss": model.loss,
                    "convergence": aggregated.get("convergence", 0.0)
                }
                round_obj.local_metrics = {
                    u.node_id: u.metrics for u in local_updates
                }
                round_obj.convergence = aggregated.get("convergence", 0.0)
                
                self._stats["rounds_completed"] += 1
                self._stats["avg_accuracy"] = (
                    self._stats["avg_accuracy"] * 0.9 + model.accuracy * 0.1
                )
                self._stats["avg_loss"] = (
                    self._stats["avg_loss"] * 0.9 + model.loss * 0.1
                )
                
                # Vérification de la convergence
                if round_obj.convergence < self.config["convergence_threshold"]:
                    self._stats["convergence_count"] += 1
                    model.status = FederatedStatus.DEPLOYED
                    logger.info(f"Model {model_id} converged at round {model.round}")
            else:
                round_obj.status = FederatedStatus.ERROR
                round_obj.metadata["error"] = "No local updates received"
            
            return round_obj
            
        except Exception as e:
            round_obj.status = FederatedStatus.ERROR
            round_obj.metadata["error"] = str(e)
            logger.error(f"Training round error: {e}")
            raise
    
    async def aggregate(
        self,
        model_id: str,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """Agrège les mises à jour."""
        with self._models_lock:
            model = self._models.get(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
        
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Vérification des signatures
        if self.config["aggregation"]["secure_aggregation"]:
            valid_updates = []
            for update in updates:
                if await self._verify_update(update):
                    valid_updates.append(update)
            updates = valid_updates
        
        if not updates:
            raise ValueError("No valid updates after verification")
        
        # Sélection de la méthode d'agrégation
        method = model.aggregation_method
        
        if method == AggregationMethod.FED_AVG:
            aggregated = await self._aggregate_fed_avg(model, updates)
        elif method == AggregationMethod.FED_PROX:
            aggregated = await self._aggregate_fed_prox(model, updates)
        elif method == AggregationMethod.FED_OPT:
            aggregated = await self._aggregate_fed_opt(model, updates)
        elif method == AggregationMethod.FED_BN:
            aggregated = await self._aggregate_fed_bn(model, updates)
        elif method == AggregationMethod.FED_MA:
            aggregated = await self._aggregate_fed_ma(model, updates)
        elif method == AggregationMethod.SCAFFOLD:
            aggregated = await self._aggregate_scaffold(model, updates)
        else:
            # Fallback sur FedAvg
            aggregated = await self._aggregate_fed_avg(model, updates)
        
        return aggregated
    
    # ========== MÉTHODES PRIVÉES - AGRÉGATION ==========
    
    async def _aggregate_fed_avg(
        self,
        model: FederatedModel,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """FedAvg: moyenne pondérée des paramètres."""
        # Calcul des poids
        weights = self._calculate_weights(updates)
        
        # Agrégation des paramètres
        aggregated_params = {}
        for update in updates:
            for key, value in update.parameters.items():
                if key not in aggregated_params:
                    aggregated_params[key] = np.zeros_like(value)
                aggregated_params[key] += value * weights[update.node_id]
        
        # Calcul des métriques
        accuracies = [u.metrics.get("accuracy", 0.0) for u in updates]
        losses = [u.metrics.get("loss", 0.0) for u in updates]
        
        return {
            "model": aggregated_params,
            "accuracy": np.mean(accuracies),
            "loss": np.mean(losses),
            "convergence": self._calculate_convergence(model, aggregated_params),
            "participants": len(updates)
        }
    
    async def _aggregate_fed_prox(
        self,
        model: FederatedModel,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """FedProx: FedAvg avec régularisation proximale."""
        mu = 0.001  # Coefficient de régularisation
        
        # Agrégation standard
        result = await self._aggregate_fed_avg(model, updates)
        
        # Ajout de la régularisation proximale
        global_params = model.global_model
        if global_params:
            for key in result["model"]:
                if key in global_params:
                    # Proximal term
                    result["model"][key] = (
                        result["model"][key] + mu * global_params[key]
                    ) / (1 + mu)
        
        return result
    
    async def _aggregate_fed_opt(
        self,
        model: FederatedModel,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """FedOpt: FedAvg avec optimisation adaptative."""
        # Agrégation standard
        result = await self._aggregate_fed_avg(model, updates)
        
        # Optimisation adaptative
        if hasattr(self, "_momentum"):
            for key in result["model"]:
                if key not in self._momentum:
                    self._momentum[key] = np.zeros_like(result["model"][key])
                
                # Momentum
                self._momentum[key] = 0.9 * self._momentum[key] + 0.1 * result["model"][key]
                result["model"][key] = self._momentum[key]
        else:
            self._momentum = {}
        
        return result
    
    async def _aggregate_fed_bn(
        self,
        model: FederatedModel,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """FedBN: FedAvg avec Batch Normalization."""
        # Séparation des paramètres BN
        bn_params = {}
        other_params = {}
        
        for update in updates:
            for key, value in update.parameters.items():
                if "bn" in key.lower() or "batch_norm" in key.lower():
                    if key not in bn_params:
                        bn_params[key] = []
                    bn_params[key].append(value)
                else:
                    if key not in other_params:
                        other_params[key] = np.zeros_like(value)
                    other_params[key] += value
        
        # Agrégation des paramètres non-BN
        aggregated_params = other_params.copy()
        for key in aggregated_params:
            aggregated_params[key] /= len(updates)
        
        # Conservation des paramètres BN locaux
        # (dans FedBN, on garde les paramètres BN locaux)
        
        # Métriques
        accuracies = [u.metrics.get("accuracy", 0.0) for u in updates]
        losses = [u.metrics.get("loss", 0.0) for u in updates]
        
        return {
            "model": aggregated_params,
            "accuracy": np.mean(accuracies),
            "loss": np.mean(losses),
            "convergence": self._calculate_convergence(model, aggregated_params),
            "participants": len(updates)
        }
    
    async def _aggregate_fed_ma(
        self,
        model: FederatedModel,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """FedMA: FedAvg avec Matching Averaging."""
        # Tri des participants par performance
        sorted_updates = sorted(
            updates,
            key=lambda u: u.metrics.get("accuracy", 0.0),
            reverse=True
        )
        
        # Matching des couches
        matched_params = {}
        
        # Prendre le meilleur modèle comme base
        best_params = sorted_updates[0].parameters
        
        for i, update in enumerate(sorted_updates[1:], 1):
            for key in best_params:
                if key not in matched_params:
                    matched_params[key] = best_params[key] * 0.5 + update.parameters[key] * 0.5
                else:
                    # Matching progressif
                    alpha = 1.0 / (i + 1)
                    matched_params[key] = (
                        matched_params[key] * (1 - alpha) +
                        update.parameters[key] * alpha
                    )
        
        # Métriques
        accuracies = [u.metrics.get("accuracy", 0.0) for u in updates]
        losses = [u.metrics.get("loss", 0.0) for u in updates]
        
        return {
            "model": matched_params,
            "accuracy": np.mean(accuracies),
            "loss": np.mean(losses),
            "convergence": self._calculate_convergence(model, matched_params),
            "participants": len(updates)
        }
    
    async def _aggregate_scaffold(
        self,
        model: FederatedModel,
        updates: List[FederatedUpdate]
    ) -> Dict[str, Any]:
        """SCAFFOLD: FedAvg avec corrections."""
        # Agrégation standard
        result = await self._aggregate_fed_avg(model, updates)
        
        # Corrections SCAFFOLD
        # Dans un système réel, on maintiendrait des contrôleurs pour chaque client
        if hasattr(self, "_control_variates"):
            for key in result["model"]:
                if key in self._control_variates:
                    # Correction du gradient
                    result["model"][key] += self._control_variates[key]
        else:
            self._control_variates = {}
        
        return result
    
    # ========== MÉTHODES PRIVÉES - ENTRAÎNEMENT ==========
    
    async def _select_participants(self, model: FederatedModel) -> List[FederatedNode]:
        """Sélectionne les participants pour un round."""
        with self._nodes_lock:
            nodes = list(self._nodes.values())
            
            # Filtrage des nœuds disponibles
            available_nodes = [
                n for n in nodes
                if n.role == FederatedRole.CLIENT
                and n.status == FederatedStatus.INITIALIZED
                and n.reliability_score > 0.5
            ]
            
            # Sélection aléatoire
            selected_count = min(
                len(available_nodes),
                self.config["max_participants"]
            )
            
            # Pondération par fiabilité
            weights = [n.reliability_score for n in available_nodes]
            selected = np.random.choice(
                available_nodes,
                size=selected_count,
                p=np.array(weights) / np.sum(weights),
                replace=False
            )
            
            return list(selected)
    
    async def _train_locally(
        self,
        model: FederatedModel,
        node: FederatedNode,
        round_number: int
    ) -> Optional[FederatedUpdate]:
        """Entraîne le modèle localement sur un nœud."""
        try:
            # Simulation d'entraînement local
            # Dans un système réel, on enverrait le modèle au nœud
            # et on récupérerait les mises à jour
            
            # Simulation: génération de paramètres aléatoires
            local_params = model.global_model.copy() if model.global_model else {}
            
            # Simulation d'apprentissage
            for key in local_params:
                if isinstance(local_params[key], np.ndarray):
                    # Ajout de bruit pour simuler l'apprentissage
                    noise = np.random.normal(0, 0.01, local_params[key].shape)
                    local_params[key] = local_params[key] + noise
            
            # Simulation des métriques
            metrics = {
                "accuracy": 0.7 + np.random.random() * 0.2,
                "loss": 0.2 + np.random.random() * 0.2,
                "local_epochs": self.config["model"]["local_epochs"],
                "batch_size": self.config["model"]["default_batch_size"]
            }
            
            # Application de la confidentialité différentielle
            if model.privacy_method == PrivacyMethod.DIFFERENTIAL_PRIVACY:
                local_params = await self._apply_differential_privacy(
                    local_params,
                    model.privacy_epsilon,
                    model.privacy_delta
                )
            
            # Création de la mise à jour
            update = FederatedUpdate(
                model_id=model.model_id,
                node_id=node.node_id,
                round_number=round_number,
                parameters=local_params,
                metrics=metrics,
                weight=node.weight
            )
            
            # Signature
            if self.encryption_engine:
                signature = await self.encryption_engine.sign(
                    pickle.dumps(update.parameters),
                    "signing_key"
                )
                update.signature = base64.b64encode(signature).decode()
            
            # Stockage de la mise à jour
            with self._updates_lock:
                self._updates[model.model_id].append(update)
            
            logger.debug(f"Local training completed: node={node.node_id}, "
                        f"accuracy={metrics['accuracy']:.4f}")
            
            return update
            
        except Exception as e:
            logger.error(f"Local training error for node {node.node_id}: {e}")
            return None
    
    async def _initialize_model(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialise un modèle."""
        # Simulation d'initialisation de modèle
        # Dans un système réel, on utiliserait PyTorch/TensorFlow
        
        model_params = {}
        for i in range(10):  # 10 couches simulées
            model_params[f"layer_{i}_weight"] = np.random.normal(0, 0.1, (10, 10))
            model_params[f"layer_{i}_bias"] = np.zeros(10)
        
        return model_params
    
    async def _apply_differential_privacy(
        self,
        parameters: Dict[str, Any],
        epsilon: float,
        delta: float
    ) -> Dict[str, Any]:
        """Applique la confidentialité différentielle."""
        # Sensibilité = 1.0 (clip norm)
        sensitivity = self.config["privacy"]["clip_norm"]
        noise_scale = sensitivity * np.sqrt(2 * np.log(1.25 / delta)) / epsilon
        
        noisy_params = {}
        for key, value in parameters.items():
            if isinstance(value, np.ndarray):
                noise = np.random.normal(0, noise_scale, value.shape)
                noisy_params[key] = value + noise
            else:
                noisy_params[key] = value
        
        return noisy_params
    
    async def _verify_update(self, update: FederatedUpdate) -> bool:
        """Vérifie une mise à jour."""
        if not update.signature:
            return False
        
        try:
            signature = base64.b64decode(update.signature)
            
            # Récupération de la clé publique du nœud
            with self._nodes_lock:
                node = self._nodes.get(update.node_id)
                if not node or not node.public_key:
                    return False
            
            # Vérification
            if self.encryption_engine:
                return await self.encryption_engine.verify(
                    pickle.dumps(update.parameters),
                    signature,
                    node.public_key
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Update verification error: {e}")
            return False
    
    def _calculate_weights(self, updates: List[FederatedUpdate]) -> Dict[str, float]:
        """Calcule les poids des mises à jour."""
        method = self.config["aggregation"]["client_weights"]
        
        if method == "uniform":
            weight = 1.0 / len(updates)
            return {u.node_id: weight for u in updates}
        
        elif method == "data_size":
            total_size = sum(u.metadata.get("data_size", 100) for u in updates)
            return {
                u.node_id: u.metadata.get("data_size", 100) / total_size
                for u in updates
            }
        
        elif method == "performance":
            total_perf = sum(u.metrics.get("accuracy", 0.0) for u in updates)
            if total_perf == 0:
                total_perf = len(updates)
            return {
                u.node_id: max(0.01, u.metrics.get("accuracy", 0.0) / total_perf)
                for u in updates
            }
        
        else:
            # Uniform par défaut
            weight = 1.0 / len(updates)
            return {u.node_id: weight for u in updates}
    
    def _calculate_convergence(
        self,
        model: FederatedModel,
        new_params: Dict[str, Any]
    ) -> float:
        """Calcule la convergence des paramètres."""
        if not model.global_model:
            return 1.0
        
        # Calcul de la distance entre les paramètres
        total_diff = 0.0
        total_norm = 0.0
        
        for key in new_params:
            if key in model.global_model:
                diff = np.linalg.norm(
                    np.array(new_params[key]) - np.array(model.global_model[key])
                )
                norm = np.linalg.norm(np.array(new_params[key]))
                total_diff += diff
                total_norm += norm
        
        if total_norm == 0:
            return 0.0
        
        return total_diff / total_norm
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _heartbeat_loop(self) -> None:
        """Boucle de heartbeat."""
        while self._is_running:
            await asyncio.sleep(30)
            
            try:
                with self._nodes_lock:
                    now = datetime.now(timezone.utc)
                    for node in list(self._nodes.values()):
                        # Vérification de la récence du heartbeat
                        age = (now - node.last_heartbeat).total_seconds()
                        if age > 120:  # 2 minutes
                            node.status = FederatedStatus.STOPPED
                            node.reliability_score *= 0.9
                
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _update_monitor_loop(self) -> None:
        """Boucle de monitoring des mises à jour."""
        while self._is_running:
            await asyncio.sleep(self.config["aggregation_interval"])
            
            try:
                # Vérification des modèles en attente
                with self._models_lock:
                    for model_id, model in self._models.items():
                        if model.status == FederatedStatus.TRAINING:
                            # Vérification du temps écoulé
                            if model.updated_at:
                                age = (datetime.now(timezone.utc) - model.updated_at).total_seconds()
                                if age > self.config["round_timeout"]:
                                    logger.warning(f"Model {model_id} training timed out")
                                    model.status = FederatedStatus.ERROR
                
            except Exception as e:
                logger.error(f"Update monitor error: {e}")
    
    async def _performance_analyzer_loop(self) -> None:
        """Boucle d'analyse de performance."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._models_lock:
                    if self._models:
                        accuracies = [m.accuracy for m in self._models.values()]
                        losses = [m.loss for m in self._models.values()]
                        
                        self._stats["avg_accuracy"] = np.mean(accuracies) if accuracies else 0.0
                        self._stats["avg_loss"] = np.mean(losses) if losses else 0.0
                
            except Exception as e:
                logger.error(f"Performance analyzer error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_model(self, model_id: str) -> Optional[FederatedModel]:
        """Récupère un modèle."""
        with self._models_lock:
            return self._models.get(model_id)
    
    async def get_models(self) -> List[FederatedModel]:
        """Récupère tous les modèles."""
        with self._models_lock:
            return list(self._models.values())
    
    async def get_round(self, round_id: str) -> Optional[FederatedRound]:
        """Récupère un round."""
        with self._rounds_lock:
            return self._rounds.get(round_id)
    
    async def get_rounds(self, model_id: Optional[str] = None) -> List[FederatedRound]:
        """Récupère les rounds."""
        with self._rounds_lock:
            rounds = list(self._rounds.values())
            if model_id:
                rounds = [r for r in rounds if r.model_id == model_id]
            return sorted(rounds, key=lambda r: r.round_number)
    
    async def get_updates(self, model_id: str, node_id: Optional[str] = None) -> List[FederatedUpdate]:
        """Récupère les mises à jour."""
        with self._updates_lock:
            updates = self._updates.get(model_id, [])
            if node_id:
                updates = [u for u in updates if u.node_id == node_id]
            return updates
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._nodes_lock:
            self._stats["active_nodes"] = len([
                n for n in self._nodes.values()
                if n.status != FederatedStatus.STOPPED
            ])
        with self._models_lock:
            self._stats["active_models"] = len([
                m for m in self._models.values()
                if m.status not in [FederatedStatus.STOPPED, FederatedStatus.ERROR]
            ])
        
        return self._stats.copy()


# ============== FEDERATED DATASET ==============

class FederatedDataset:
    """
    Dataset fédéré pour l'apprentissage distribué.
    Permet le partitionnement des données entre les participants.
    """
    
    def __init__(self, data: Any, num_clients: int = 10, iid: bool = True):
        self.data = data
        self.num_clients = num_clients
        self.iid = iid
        self._partitions = None
        self._partition_lock = threading.RLock()
    
    def partition(self) -> List[Any]:
        """Partitionne les données entre les clients."""
        with self._partition_lock:
            if self._partitions is None:
                self._partitions = self._create_partitions()
            return self._partitions
    
    def _create_partitions(self) -> List[Any]:
        """Crée les partitions de données."""
        if isinstance(self.data, pd.DataFrame):
            return self._partition_dataframe()
        elif isinstance(self.data, np.ndarray):
            return self._partition_array()
        else:
            # Partition générique
            total = len(self.data)
            chunk_size = total // self.num_clients
            return [
                self.data[i * chunk_size:(i + 1) * chunk_size]
                for i in range(self.num_clients)
            ]
    
    def _partition_dataframe(self) -> List[pd.DataFrame]:
        """Partitionne un DataFrame."""
        if self.iid:
            # IID: distribution aléatoire
            indices = np.random.permutation(len(self.data))
            chunk_size = len(self.data) // self.num_clients
            partitions = []
            
            for i in range(self.num_clients):
                start = i * chunk_size
                end = (i + 1) * chunk_size if i < self.num_clients - 1 else len(self.data)
                partition_indices = indices[start:end]
                partitions.append(self.data.iloc[partition_indices])
            
            return partitions
        
        else:
            # Non-IID: distribution par classes
            # Simulation de Non-IID
            partitions = []
            for i in range(self.num_clients):
                # Échantillonnage biaisé
                start = i * len(self.data) // self.num_clients
                end = (i + 1) * len(self.data) // self.num_clients
                partitions.append(self.data.iloc[start:end])
            
            return partitions
    
    def _partition_array(self) -> List[np.ndarray]:
        """Partitionne un tableau numpy."""
        total = len(self.data)
        chunk_size = total // self.num_clients
        return [
            self.data[i * chunk_size:(i + 1) * chunk_size]
            for i in range(self.num_clients)
        ]
    
    def get_client_data(self, client_id: int) -> Any:
        """Récupère les données pour un client."""
        partitions = self.partition()
        if 0 <= client_id < len(partitions):
            return partitions[client_id]
        return None


# ============== FACTORY ==============

class FederatedFactory:
    """Factory pour créer des composants fédérés."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> FederatedEngine:
        """Crée un moteur fédéré."""
        if not encryption_engine:
            encryption_engine = await EncryptionFactory.create_engine()
        
        engine = FederatedEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_dataset(
        data: Any,
        num_clients: int = 10,
        iid: bool = True
    ) -> FederatedDataset:
        """Crée un dataset fédéré."""
        return FederatedDataset(data, num_clients, iid)
    
    @staticmethod
    def create_node(
        node_id: Optional[str] = None,
        role: FederatedRole = FederatedRole.CLIENT,
        name: str = "",
        endpoint: str = "",
        public_key: Optional[str] = None
    ) -> FederatedNode:
        """Crée un nœud fédéré."""
        return FederatedNode(
            node_id=node_id or str(uuid.uuid4()),
            role=role,
            name=name,
            endpoint=endpoint,
            public_key=public_key
        )


# ============== EXPORT ==============

__all__ = [
    "FederatedRole",
    "FederatedStatus",
    "AggregationMethod",
    "PrivacyMethod",
    "FederatedNode",
    "FederatedModel",
    "FederatedRound",
    "FederatedUpdate",
    "FederatedEngineInterface",
    "FederatedEngine",
    "FederatedDataset",
    "FederatedFactory"
]

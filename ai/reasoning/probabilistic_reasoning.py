# ai/reasoning/probabilistic_reasoning.py
"""
NEXUS AI TRADING SYSTEM - Probabilistic Reasoning Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import json
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ProbabilisticNode:
    """Nœud dans un réseau probabiliste"""
    name: str
    distribution: Dict[Any, float]  # Distribution de probabilité
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    cpt: Optional[Dict[Any, Dict[Any, float]]] = None  # Table de probabilité conditionnelle
    evidence: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'distribution': self.distribution,
            'parents': self.parents,
            'children': self.children,
            'cpt': self.cpt,
            'evidence': self.evidence,
        }


@dataclass
class BayesianNetwork:
    """Réseau bayésien"""
    nodes: Dict[str, ProbabilisticNode]
    edges: List[Tuple[str, str]]
    name: str = "bayesian_network"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'nodes': {k: v.to_dict() for k, v in self.nodes.items()},
            'edges': self.edges,
        }


@dataclass
class InferenceResult:
    """Résultat d'inférence probabiliste"""
    query: Dict[str, Any]
    posterior: Dict[str, Dict[Any, float]]
    evidence: Dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'posterior': self.posterior,
            'evidence': self.evidence,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
        }


class ProbabilisticReasoning:
    """
    Moteur de raisonnement probabiliste pour l'IA de trading.

    Features:
    - Bayesian networks
    - Belief propagation
    - Variable elimination
    - Monte Carlo sampling
    - Evidence integration

    Example:
        ```python
        engine = ProbabilisticReasoning()

        # Create Bayesian network
        nodes = {
            'market': ProbabilisticNode(
                name='market',
                distribution={'bull': 0.6, 'bear': 0.4}
            ),
            'signal': ProbabilisticNode(
                name='signal',
                distribution={'buy': 0.5, 'sell': 0.5},
                parents=['market']
            )
        }
        engine.build_bayesian_network(nodes, [('market', 'signal')])

        # Inference
        result = engine.infer(query={'signal': None}, evidence={'market': 'bull'})
        ```
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.bayesian_network: Optional[BayesianNetwork] = None
        self.factors: Dict[str, Any] = {}
        self.evidence: Dict[str, Any] = {}
        self.queries: List[Dict[str, Any]] = []
        self.results: List[InferenceResult] = []
        self.sampler = None

        # Configuration
        self.sampling_method = self.config.get('sampling_method', 'rejection')
        self.n_samples = self.config.get('n_samples', 10000)
        self.n_burnin = self.config.get('n_burnin', 1000)
        self.n_chains = self.config.get('n_chains', 4)

        logger.info(f"ProbabilisticReasoning initialisé")

    def build_bayesian_network(
        self,
        nodes: Dict[str, ProbabilisticNode],
        edges: List[Tuple[str, str]]
    ) -> None:
        """
        Construit un réseau bayésien.

        Args:
            nodes: Nœuds du réseau
            edges: Arêtes du réseau
        """
        self.bayesian_network = BayesianNetwork(nodes=nodes, edges=edges)

        # Validation du réseau
        self._validate_network()

        # Initialisation des facteurs
        self._initialize_factors()

        logger.info(f"Réseau bayésien construit: {len(nodes)} nœuds, {len(edges)} arêtes")

    def _validate_network(self):
        """Valide le réseau bayésien"""
        if not self.bayesian_network:
            return

        # Vérification des cycles
        if NETWORKX_AVAILABLE:
            G = nx.DiGraph()
            G.add_edges_from(self.bayesian_network.edges)

            if not nx.is_directed_acyclic_graph(G):
                logger.warning("Le réseau bayésien contient des cycles")

        # Vérification des distributions
        for node in self.bayesian_network.nodes.values():
            if node.distribution and sum(node.distribution.values()) != 1.0:
                logger.warning(f"Distribution du nœud {node.name} ne somme pas à 1")

    def _initialize_factors(self):
        """Initialise les facteurs du réseau"""
        self.factors = {}

        for node in self.bayesian_network.nodes.values():
            if node.distribution:
                self.factors[node.name] = node.distribution

    def add_evidence(self, evidence: Dict[str, Any]) -> None:
        """
        Ajoute des preuves.

        Args:
            evidence: Dictionnaire des preuves
        """
        self.evidence.update(evidence)

        # Mise à jour des nœuds
        if self.bayesian_network:
            for node_name, value in evidence.items():
                if node_name in self.bayesian_network.nodes:
                    self.bayesian_network.nodes[node_name].evidence = value

        logger.info(f"Preuves ajoutées: {evidence}")

    def infer(
        self,
        query: Dict[str, Any],
        evidence: Optional[Dict[str, Any]] = None,
        method: str = 'variable_elimination'
    ) -> InferenceResult:
        """
        Effectue une inférence probabiliste.

        Args:
            query: Variables à inférer
            evidence: Preuves (optionnel)
            method: Méthode d'inférence

        Returns:
            InferenceResult: Résultat de l'inférence
        """
        if evidence:
            self.add_evidence(evidence)

        if method == 'variable_elimination':
            posterior = self._variable_elimination(query)
        elif method == 'belief_propagation':
            posterior = self._belief_propagation(query)
        elif method == 'monte_carlo':
            posterior = self._monte_carlo_sampling(query)
        else:
            raise ValueError(f"Méthode non supportée: {method}")

        # Calcul de la confiance
        confidence = self._compute_confidence(posterior)

        result = InferenceResult(
            query=query,
            posterior=posterior,
            evidence=self.evidence,
            confidence=confidence,
        )

        self.results.append(result)

        logger.info(f"Inférence terminée: {len(posterior)} variables inférées")

        return result

    def _variable_elimination(self, query: Dict[str, Any]) -> Dict[str, Dict[Any, float]]:
        """
        Inférence par élimination de variables.

        Args:
            query: Variables à inférer

        Returns:
            Dict[str, Dict[Any, float]]: Distributions postérieures
        """
        if not self.bayesian_network:
            return {}

        posterior = {}
        variables = list(query.keys())

        for var in variables:
            if var in self.bayesian_network.nodes:
                node = self.bayesian_network.nodes[var]

                if node.distribution and not node.parents:
                    # Nœud sans parents
                    posterior[var] = node.distribution
                elif node.cpt and node.parents:
                    # Nœud avec parents
                    if all(p in self.evidence for p in node.parents):
                        # Tous les parents observés
                        evidence_tuple = tuple(self.evidence[p] for p in node.parents)
                        if evidence_tuple in node.cpt:
                            posterior[var] = node.cpt[evidence_tuple]
                        else:
                            posterior[var] = node.distribution
                    else:
                        posterior[var] = node.distribution
                else:
                    posterior[var] = node.distribution

        return posterior

    def _belief_propagation(self, query: Dict[str, Any]) -> Dict[str, Dict[Any, float]]:
        """
        Inférence par propagation de croyances.

        Args:
            query: Variables à inférer

        Returns:
            Dict[str, Dict[Any, float]]: Distributions postérieures
        """
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX non disponible, fallback à l'élimination de variables")
            return self._variable_elimination(query)

        if not self.bayesian_network:
            return {}

        # Construction du graphe
        G = nx.DiGraph()
        G.add_edges_from(self.bayesian_network.edges)

        posterior = {}
        variables = list(query.keys())

        for var in variables:
            if var in self.bayesian_network.nodes:
                node = self.bayesian_network.nodes[var]

                # Calcul de la croyance simplifié
                belief = node.distribution.copy()

                # Intégration des preuves
                for evidence_var, evidence_value in self.evidence.items():
                    if evidence_var in node.parents:
                        # Mise à jour de la croyance
                        evidence_index = node.parents.index(evidence_var)
                        if node.cpt:
                            filtered_cpt = {
                                k: v for k, v in node.cpt.items()
                                if k[evidence_index] == evidence_value
                            }
                            if filtered_cpt:
                                total = sum(filtered_cpt.values())
                                if total > 0:
                                    belief = {
                                        k: v / total
                                        for k, v in filtered_cpt.items()
                                    }

                posterior[var] = belief

        return posterior

    def _monte_carlo_sampling(self, query: Dict[str, Any]) -> Dict[str, Dict[Any, float]]:
        """
        Inférence par échantillonnage Monte Carlo.

        Args:
            query: Variables à inférer

        Returns:
            Dict[str, Dict[Any, float]]: Distributions postérieures
        """
        if not self.bayesian_network:
            return {}

        samples = []
        variables = list(query.keys())

        # Échantillonnage
        for _ in range(self.n_samples):
            sample = self._sample_network()
            samples.append(sample)

        # Calcul des distributions postérieures
        posterior = {}

        for var in variables:
            if var in self.bayesian_network.nodes:
                values = [s[var] for s in samples if var in s]
                if values:
                    distribution = {}
                    for val in set(values):
                        distribution[val] = values.count(val) / len(values)
                    posterior[var] = distribution
                else:
                    node = self.bayesian_network.nodes[var]
                    posterior[var] = node.distribution

        return posterior

    def _sample_network(self) -> Dict[str, Any]:
        """
        Échantillonne le réseau bayésien.

        Returns:
            Dict[str, Any]: Échantillon
        """
        sample = {}

        if not self.bayesian_network:
            return sample

        # Échantillonnage des nœuds
        for node in self.bayesian_network.nodes.values():
            if not node.parents:
                # Nœud sans parents
                values = list(node.distribution.keys())
                probs = list(node.distribution.values())
                sample[node.name] = np.random.choice(values, p=probs)
            else:
                # Nœud avec parents
                parent_values = tuple(sample[p] for p in node.parents if p in sample)
                if node.cpt and parent_values in node.cpt:
                    values = list(node.cpt[parent_values].keys())
                    probs = list(node.cpt[parent_values].values())
                    sample[node.name] = np.random.choice(values, p=probs)
                else:
                    values = list(node.distribution.keys())
                    probs = list(node.distribution.values())
                    sample[node.name] = np.random.choice(values, p=probs)

        return sample

    def _compute_confidence(self, posterior: Dict[str, Dict[Any, float]]) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            posterior: Distributions postérieures

        Returns:
            float: Niveau de confiance
        """
        if not posterior:
            return 0.0

        # Confiance basée sur l'entropie des distributions
        confidences = []
        for dist in posterior.values():
            probs = list(dist.values())
            if probs:
                entropy = -sum(p * np.log(p) for p in probs if p > 0)
                max_entropy = np.log(len(probs))
                confidence = 1 - (entropy / max_entropy) if max_entropy > 0 else 0.5
                confidences.append(confidence)

        return np.mean(confidences) if confidences else 0.5

    def get_network_structure(self) -> Dict[str, Any]:
        """
        Retourne la structure du réseau.

        Returns:
            Dict[str, Any]: Structure du réseau
        """
        if not self.bayesian_network:
            return {}

        return {
            'nodes': list(self.bayesian_network.nodes.keys()),
            'edges': self.bayesian_network.edges,
            'node_count': len(self.bayesian_network.nodes),
            'edge_count': len(self.bayesian_network.edges),
            'name': self.bayesian_network.name,
            'description': self.bayesian_network.description,
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le moteur probabiliste.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config,
                'bayesian_network': self.bayesian_network.to_dict() if self.bayesian_network else None,
                'evidence': self.evidence,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Moteur probabiliste sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'ProbabilisticReasoning':
        """
        Charge un moteur probabiliste.

        Args:
            filepath: Chemin du fichier

        Returns:
            ProbabilisticReasoning: Moteur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            engine = cls(data.get('config', {}))

            # Restaurer le réseau bayésien
            network_data = data.get('bayesian_network')
            if network_data:
                nodes = {
                    name: ProbabilisticNode(
                        name=name,
                        distribution=node_data.get('distribution', {}),
                        parents=node_data.get('parents', []),
                        children=node_data.get('children', []),
                        cpt=node_data.get('cpt'),
                        evidence=node_data.get('evidence'),
                    )
                    for name, node_data in network_data['nodes'].items()
                }
                engine.bayesian_network = BayesianNetwork(
                    nodes=nodes,
                    edges=network_data['edges'],
                    name=network_data.get('name', 'bayesian_network'),
                    description=network_data.get('description', ''),
                )

            engine.evidence = data.get('evidence', {})

            logger.info(f"Moteur probabiliste chargé: {filepath}")
            return engine

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_probabilistic_engine(
    sampling_method: str = 'rejection',
    n_samples: int = 10000,
    **kwargs
) -> ProbabilisticReasoning:
    """
    Factory pour créer un moteur probabiliste.

    Args:
        sampling_method: Méthode d'échantillonnage
        n_samples: Nombre d'échantillons
        **kwargs: Arguments supplémentaires

    Returns:
        ProbabilisticReasoning: Moteur probabiliste
    """
    config = {
        'sampling_method': sampling_method,
        'n_samples': n_samples,
        **kwargs
    }
    return ProbabilisticReasoning(config)


__all__ = [
    'ProbabilisticReasoning',
    'ProbabilisticNode',
    'BayesianNetwork',
    'InferenceResult',
    'create_probabilistic_engine',
]

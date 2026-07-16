# ai/reasoning/inference_engine.py
"""
NEXUS AI TRADING SYSTEM - Inference Engine
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import json
import time
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class InferenceRule:
    """Règle d'inférence"""
    name: str
    condition: Callable
    action: Callable
    priority: int = 0
    weight: float = 1.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'priority': self.priority,
            'weight': self.weight,
            'description': self.description,
        }


@dataclass
class InferenceResult:
    """Résultat d'inférence"""
    conclusion: Any
    confidence: float
    rules_applied: List[str]
    reasoning: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'conclusion': self.conclusion,
            'confidence': self.confidence,
            'rules_applied': self.rules_applied,
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat(),
        }


class InferenceEngine:
    """
    Moteur d'inférence pour l'IA de trading.

    Features:
    - Rule-based reasoning
    - Forward chaining
    - Backward chaining
    - Uncertainty handling
    - Conflict resolution
    - Explanation generation

    Example:
        ```python
        engine = InferenceEngine()

        # Add rules
        def condition(data):
            return data['rsi'] < 30

        def action(data):
            return {'signal': 'buy', 'reason': 'oversold'}

        engine.add_rule(
            name='oversold',
            condition=condition,
            action=action,
            priority=1
        )

        # Run inference
        result = engine.infer(data)
        ```
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: List[InferenceRule] = []
        self.facts: Dict[str, Any] = {}
        self.knowledge_base: Dict[str, Any] = {}
        self.working_memory: Dict[str, Any] = {}
        self.result_history: List[InferenceResult] = []

        # Configuration
        self.max_rules = self.config.get('max_rules', 100)
        self.max_iterations = self.config.get('max_iterations', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.5)
        self.conflict_resolution = self.config.get('conflict_resolution', 'priority')

        logger.info(f"InferenceEngine initialisé avec {len(self.rules)} règles")

    def add_rule(
        self,
        name: str,
        condition: Callable,
        action: Callable,
        priority: int = 0,
        weight: float = 1.0,
        description: str = ""
    ) -> None:
        """
        Ajoute une règle d'inférence.

        Args:
            name: Nom de la règle
            condition: Fonction de condition
            action: Fonction d'action
            priority: Priorité (plus élevé = plus important)
            weight: Poids de la règle
            description: Description de la règle
        """
        rule = InferenceRule(
            name=name,
            condition=condition,
            action=action,
            priority=priority,
            weight=weight,
            description=description
        )
        self.rules.append(rule)

        # Trier par priorité
        self.rules.sort(key=lambda x: -x.priority)

        logger.info(f"Règle ajoutée: {name} (priority={priority})")

    def remove_rule(self, name: str) -> bool:
        """
        Supprime une règle.

        Args:
            name: Nom de la règle

        Returns:
            bool: True si supprimée
        """
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                logger.info(f"Règle supprimée: {name}")
                return True
        return False

    def add_fact(self, key: str, value: Any) -> None:
        """
        Ajoute un fait à la base de connaissances.

        Args:
            key: Clé du fait
            value: Valeur du fait
        """
        self.facts[key] = value
        logger.debug(f"Fait ajouté: {key}={value}")

    def add_facts(self, facts: Dict[str, Any]) -> None:
        """
        Ajoute plusieurs faits.

        Args:
            facts: Dictionnaire des faits
        """
        self.facts.update(facts)
        logger.debug(f"{len(facts)} faits ajoutés")

    def clear_facts(self) -> None:
        """Vide les faits"""
        self.facts.clear()
        logger.debug("Faits vidés")

    def forward_chaining(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Raisonnement par chaînage avant.

        Args:
            data: Données d'entrée

        Returns:
            Dict[str, Any]: Conclusions
        """
        self.working_memory = data.copy()
        self.working_memory.update(self.facts)

        conclusions = {}
        applied_rules = []
        iterations = 0

        while iterations < self.max_iterations:
            triggered_rules = []
            new_conclusions = {}

            # Évaluation des règles
            for rule in self.rules:
                try:
                    if rule.condition(self.working_memory):
                        triggered_rules.append(rule)
                except Exception as e:
                    logger.warning(f"Erreur dans la règle {rule.name}: {e}")

            if not triggered_rules:
                break

            # Résolution des conflits
            selected_rules = self._resolve_conflicts(triggered_rules)

            # Application des règles
            for rule in selected_rules:
                try:
                    result = rule.action(self.working_memory)
                    if result:
                        if isinstance(result, dict):
                            new_conclusions.update(result)
                            self.working_memory.update(result)
                        else:
                            new_conclusions['result'] = result
                            self.working_memory['result'] = result

                        applied_rules.append(rule.name)

                except Exception as e:
                    logger.warning(f"Erreur dans l'action de {rule.name}: {e}")

            if new_conclusions:
                conclusions.update(new_conclusions)

            iterations += 1

        return conclusions

    def backward_chaining(self, goal: Any, data: Dict[str, Any]) -> bool:
        """
        Raisonnement par chaînage arrière.

        Args:
            goal: Objectif à prouver
            data: Données d'entrée

        Returns:
            bool: True si l'objectif est prouvé
        """
        self.working_memory = data.copy()
        self.working_memory.update(self.facts)

        # Vérification directe
        if self._check_goal(goal):
            return True

        # Recherche de règles
        for rule in self.rules:
            try:
                if rule.action(self.working_memory) == goal:
                    if rule.condition(self.working_memory):
                        return True
            except:
                continue

        return False

    def _resolve_conflicts(self, rules: List[InferenceRule]) -> List[InferenceRule]:
        """
        Résout les conflits entre règles.

        Args:
            rules: Liste des règles déclenchées

        Returns:
            List[InferenceRule]: Règles sélectionnées
        """
        if not rules:
            return []

        if self.conflict_resolution == 'priority':
            # Priorité la plus élevée
            max_priority = max(r.priority for r in rules)
            return [r for r in rules if r.priority == max_priority]

        elif self.conflict_resolution == 'weight':
            # Poids le plus élevé
            max_weight = max(r.weight for r in rules)
            return [r for r in rules if r.weight == max_weight]

        elif self.conflict_resolution == 'recency':
            # Règles les plus récentes
            return rules[-1:]

        else:
            # Toutes les règles
            return rules

    def _check_goal(self, goal: Any) -> bool:
        """
        Vérifie si un objectif est atteint.

        Args:
            goal: Objectif à vérifier

        Returns:
            bool: True si atteint
        """
        for value in self.working_memory.values():
            if value == goal:
                return True
        return False

    def infer(
        self,
        data: Dict[str, Any],
        method: str = 'forward'
    ) -> InferenceResult:
        """
        Effectue une inférence.

        Args:
            data: Données d'entrée
            method: Méthode d'inférence ('forward', 'backward')

        Returns:
            InferenceResult: Résultat de l'inférence
        """
        self.working_memory = data.copy()
        self.working_memory.update(self.facts)

        start_time = time.time()

        if method == 'forward':
            conclusions = self.forward_chaining(data)
        elif method == 'backward':
            # Backward chaining pour un objectif spécifique
            goal = data.get('goal')
            if goal:
                success = self.backward_chaining(goal, data)
                conclusions = {'success': success}
            else:
                conclusions = {'error': 'No goal specified for backward chaining'}
        else:
            raise ValueError(f"Méthode d'inférence non supportée: {method}")

        # Calcul de la confiance
        confidence = self._compute_confidence(conclusions)

        # Génération d'explications
        reasoning = self._generate_reasoning(conclusions)

        result = InferenceResult(
            conclusion=conclusions,
            confidence=confidence,
            rules_applied=[r.name for r in self.rules if r.name in str(conclusions)],
            reasoning=reasoning,
        )

        self.result_history.append(result)

        logger.info(f"Inférence terminée en {time.time() - start_time:.4f}s")
        logger.info(f"Conclusions: {conclusions}")

        return result

    def _compute_confidence(self, conclusions: Dict[str, Any]) -> float:
        """
        Calcule le niveau de confiance des conclusions.

        Args:
            conclusions: Conclusions

        Returns:
            float: Niveau de confiance
        """
        if not conclusions:
            return 0.0

        # Confiance basée sur le nombre de règles appliquées
        n_rules = len(self.rules)
        if n_rules > 0:
            confidence = min(1.0, len(self.rules_applied) / n_rules)
        else:
            confidence = 0.5

        # Ajustement par la qualité des données
        data_quality = 0.5
        if 'quality' in self.working_memory:
            data_quality = min(1.0, self.working_memory['quality'])

        confidence = confidence * data_quality

        return confidence

    def _generate_reasoning(self, conclusions: Dict[str, Any]) -> List[str]:
        """
        Génère des explications pour les conclusions.

        Args:
            conclusions: Conclusions

        Returns:
            List[str]: Explications
        """
        reasoning = []

        # État initial
        reasoning.append(f"État initial: {len(self.working_memory)} faits")

        # Règles appliquées
        if self.rules_applied:
            reasoning.append(f"Règles appliquées: {', '.join(self.rules_applied)}")

        # Conclusions
        for key, value in conclusions.items():
            reasoning.append(f"Conclusion: {key} = {value}")

        return reasoning

    def explain(self, result: InferenceResult) -> str:
        """
        Génère une explication détaillée d'un résultat.

        Args:
            result: Résultat d'inférence

        Returns:
            str: Explication
        """
        lines = [
            "=" * 60,
            "EXPLICATION D'INFÉRENCE",
            "=" * 60,
            f"Timestamp: {result.timestamp}",
            f"Confiance: {result.confidence:.2f}",
            "-" * 60,
            "RÉSUMÉ:",
            f"  {result.conclusion}",
            "-" * 60,
            "RAISONNEMENT:",
        ]

        for step in result.reasoning:
            lines.append(f"  - {step}")

        lines.append("-" * 60)
        lines.append(f"Règles appliquées: {len(result.rules_applied)}")

        return "\n".join(lines)

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le moteur d'inférence.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config,
                'rules': [
                    {
                        'name': r.name,
                        'priority': r.priority,
                        'weight': r.weight,
                        'description': r.description,
                    }
                    for r in self.rules
                ],
                'facts': self.facts,
                'knowledge_base': self.knowledge_base,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Moteur d'inférence sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'InferenceEngine':
        """
        Charge un moteur d'inférence.

        Args:
            filepath: Chemin du fichier

        Returns:
            InferenceEngine: Moteur d'inférence chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            engine = cls(data.get('config', {}))

            # Restaurer les faits
            engine.facts = data.get('facts', {})
            engine.knowledge_base = data.get('knowledge_base', {})

            logger.info(f"Moteur d'inférence chargé: {filepath}")
            return engine

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_inference_engine(
    confidence_threshold: float = 0.5,
    max_rules: int = 100,
    **kwargs
) -> InferenceEngine:
    """
    Factory pour créer un moteur d'inférence.

    Args:
        confidence_threshold: Seuil de confiance
        max_rules: Nombre maximum de règles
        **kwargs: Arguments supplémentaires

    Returns:
        InferenceEngine: Moteur d'inférence
    """
    config = {
        'confidence_threshold': confidence_threshold,
        'max_rules': max_rules,
        **kwargs
    }
    return InferenceEngine(config)


__all__ = [
    'InferenceEngine',
    'InferenceRule',
    'InferenceResult',
    'create_inference_engine',
]

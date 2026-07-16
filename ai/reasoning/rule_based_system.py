# ai/reasoning/rule_based_system.py
"""
NEXUS AI TRADING SYSTEM - Rule-Based System
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import json
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    """Règle du système"""
    id: str
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    action: Callable[[Dict[str, Any]], Dict[str, Any]]
    priority: int = 0
    weight: float = 1.0
    description: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'priority': self.priority,
            'weight': self.weight,
            'description': self.description,
            'enabled': self.enabled,
        }


@dataclass
class RuleResult:
    """Résultat d'exécution de règles"""
    fired_rules: List[Rule]
    conclusions: Dict[str, Any]
    confidence: float
    execution_time: float
    reasoning: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fired_rules': [r.name for r in self.fired_rules],
            'conclusions': self.conclusions,
            'confidence': self.confidence,
            'execution_time': self.execution_time,
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat(),
        }


class RuleBasedSystem:
    """
    Système basé sur des règles pour l'IA de trading.

    Features:
    - Règles conditionnelles
    - Chaînage avant/arrière
    - Résolution de conflits
    - Gestion d'incertitude
    - Explications

    Example:
        ```python
        system = RuleBasedSystem()

        def market_condition(data):
            return data.get('rsi', 50) < 30

        def market_action(data):
            return {'signal': 'buy', 'reason': 'oversold'}

        system.add_rule(
            id='buy_oversold',
            condition=market_condition,
            action=market_action,
            priority=1
        )

        result = system.run(data)
        ```
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: List[Rule] = []
        self.facts: Dict[str, Any] = {}
        self.working_memory: Dict[str, Any] = {}
        self.history: List[RuleResult] = []

        # Configuration
        self.max_rules = self.config.get('max_rules', 100)
        self.max_iterations = self.config.get('max_iterations', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.5)
        self.conflict_resolution = self.config.get('conflict_resolution', 'priority')

        logger.info(f"RuleBasedSystem initialisé")

    def add_rule(
        self,
        id: str,
        condition: Callable[[Dict[str, Any]], bool],
        action: Callable[[Dict[str, Any]], Dict[str, Any]],
        name: Optional[str] = None,
        priority: int = 0,
        weight: float = 1.0,
        description: str = ""
    ) -> None:
        """
        Ajoute une règle.

        Args:
            id: Identifiant unique
            condition: Fonction de condition
            action: Fonction d'action
            name: Nom de la règle
            priority: Priorité
            weight: Poids
            description: Description
        """
        rule = Rule(
            id=id,
            name=name or id,
            condition=condition,
            action=action,
            priority=priority,
            weight=weight,
            description=description
        )

        self.rules.append(rule)
        self.rules.sort(key=lambda x: -x.priority)

        logger.info(f"Règle ajoutée: {id}")

    def remove_rule(self, id: str) -> bool:
        """
        Supprime une règle.

        Args:
            id: Identifiant de la règle

        Returns:
            bool: True si supprimée
        """
        for i, rule in enumerate(self.rules):
            if rule.id == id:
                self.rules.pop(i)
                logger.info(f"Règle supprimée: {id}")
                return True
        return False

    def enable_rule(self, id: str, enabled: bool = True) -> bool:
        """
        Active ou désactive une règle.

        Args:
            id: Identifiant de la règle
            enabled: État d'activation

        Returns:
            bool: True si modifié
        """
        for rule in self.rules:
            if rule.id == id:
                rule.enabled = enabled
                logger.info(f"Règle {id} {'activée' if enabled else 'désactivée'}")
                return True
        return False

    def add_fact(self, key: str, value: Any) -> None:
        """Ajoute un fait"""
        self.facts[key] = value
        logger.debug(f"Fait ajouté: {key}={value}")

    def add_facts(self, facts: Dict[str, Any]) -> None:
        """Ajoute plusieurs faits"""
        self.facts.update(facts)

    def clear_facts(self) -> None:
        """Vide les faits"""
        self.facts.clear()

    def run(self, data: Dict[str, Any]) -> RuleResult:
        """
        Exécute le système de règles.

        Args:
            data: Données d'entrée

        Returns:
            RuleResult: Résultat de l'exécution
        """
        import time
        start_time = time.time()

        self.working_memory = data.copy()
        self.working_memory.update(self.facts)

        fired_rules = []
        conclusions = {}
        reasoning = []

        iteration = 0
        changed = True

        while changed and iteration < self.max_iterations:
            changed = False
            triggered_rules = []

            # Évaluation des règles
            for rule in self.rules:
                if not rule.enabled:
                    continue

                try:
                    if rule.condition(self.working_memory):
                        triggered_rules.append(rule)
                        reasoning.append(f"Règle '{rule.name}' déclenchée")
                except Exception as e:
                    logger.warning(f"Erreur dans la règle {rule.name}: {e}")
                    reasoning.append(f"Erreur dans la règle '{rule.name}': {e}")

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
                            new_conclusions = {k: v for k, v in result.items() if k not in conclusions}
                            if new_conclusions:
                                conclusions.update(new_conclusions)
                                self.working_memory.update(new_conclusions)
                                fired_rules.append(rule)
                                reasoning.append(f"Action de '{rule.name}': {new_conclusions}")
                                changed = True
                        else:
                            conclusions['result'] = result
                            self.working_memory['result'] = result
                            fired_rules.append(rule)
                            reasoning.append(f"Action de '{rule.name}': {result}")
                            changed = True

                except Exception as e:
                    logger.warning(f"Erreur dans l'action de {rule.name}: {e}")
                    reasoning.append(f"Erreur dans l'action de '{rule.name}': {e}")

            iteration += 1

        execution_time = time.time() - start_time
        confidence = self._compute_confidence(fired_rules, conclusions)

        result = RuleResult(
            fired_rules=fired_rules,
            conclusions=conclusions,
            confidence=confidence,
            execution_time=execution_time,
            reasoning=reasoning,
        )

        self.history.append(result)

        logger.info(f"Exécution terminée: {len(fired_rules)} règles, {len(conclusions)} conclusions")

        return result

    def _resolve_conflicts(self, rules: List[Rule]) -> List[Rule]:
        """
        Résout les conflits entre règles.

        Args:
            rules: Liste des règles

        Returns:
            List[Rule]: Règles sélectionnées
        """
        if not rules:
            return []

        if self.conflict_resolution == 'priority':
            max_priority = max(r.priority for r in rules)
            return [r for r in rules if r.priority == max_priority]

        elif self.conflict_resolution == 'weight':
            max_weight = max(r.weight for r in rules)
            return [r for r in rules if r.weight == max_weight]

        elif self.conflict_resolution == 'specificity':
            # Règles plus spécifiques (condition plus longue)
            rules_sorted = sorted(rules, key=lambda r: len(r.condition.__code__.co_code), reverse=True)
            return rules_sorted[:1]

        else:
            return rules

    def _compute_confidence(self, fired_rules: List[Rule], conclusions: Dict[str, Any]) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            fired_rules: Règles déclenchées
            conclusions: Conclusions

        Returns:
            float: Niveau de confiance
        """
        if not fired_rules:
            return 0.0

        # Confiance basée sur le ratio de règles déclenchées
        active_rules = [r for r in self.rules if r.enabled]
        if active_rules:
            rule_ratio = len(fired_rules) / len(active_rules)
        else:
            rule_ratio = 0.5

        # Confiance basée sur la qualité des données
        data_quality = 0.5
        if 'quality' in self.working_memory:
            data_quality = min(1.0, self.working_memory['quality'])

        confidence = 0.6 * rule_ratio + 0.4 * data_quality
        confidence = min(1.0, confidence)

        return confidence

    def explain(self, result: RuleResult) -> str:
        """
        Génère une explication détaillée.

        Args:
            result: Résultat de l'exécution

        Returns:
            str: Explication
        """
        lines = [
            "=" * 60,
            "EXPLICATION DU SYSTÈME DE RÈGLES",
            "=" * 60,
            f"Timestamp: {result.timestamp}",
            f"Temps d'exécution: {result.execution_time:.4f}s",
            f"Confiance: {result.confidence:.2f}",
            "-" * 60,
            "RÈGLES DÉCLENCHÉES:",
        ]

        for rule in result.fired_rules:
            lines.append(f"  - {rule.name} (priorité: {rule.priority})")

        lines.append("-" * 60)
        lines.append("CONCLUSIONS:")

        for key, value in result.conclusions.items():
            lines.append(f"  {key} = {value}")

        lines.append("-" * 60)
        lines.append("RAISONNEMENT:")

        for step in result.reasoning:
            lines.append(f"  - {step}")

        return "\n".join(lines)

    def get_rules(self) -> List[Dict[str, Any]]:
        """
        Retourne les règles.

        Returns:
            List[Dict[str, Any]]: Liste des règles
        """
        return [
            {
                'id': r.id,
                'name': r.name,
                'priority': r.priority,
                'weight': r.weight,
                'description': r.description,
                'enabled': r.enabled,
            }
            for r in self.rules
        ]

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le système de règles.

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
                        'id': r.id,
                        'name': r.name,
                        'priority': r.priority,
                        'weight': r.weight,
                        'description': r.description,
                        'enabled': r.enabled,
                    }
                    for r in self.rules
                ],
                'facts': self.facts,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Système de règles sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'RuleBasedSystem':
        """
        Charge un système de règles.

        Args:
            filepath: Chemin du fichier

        Returns:
            RuleBasedSystem: Système chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            system = cls(data.get('config', {}))

            # Restaurer les règles
            for rule_data in data.get('rules', []):
                # Note: Les fonctions condition/action ne peuvent pas être sauvegardées
                # Elles doivent être redéfinies
                logger.warning(f"Règle {rule_data['id']} chargée sans condition/action")

            system.facts = data.get('facts', {})

            logger.info(f"Système de règles chargé: {filepath}")
            return system

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_rule_system(
    conflict_resolution: str = 'priority',
    confidence_threshold: float = 0.5,
    **kwargs
) -> RuleBasedSystem:
    """
    Factory pour créer un système de règles.

    Args:
        conflict_resolution: Méthode de résolution de conflits
        confidence_threshold: Seuil de confiance
        **kwargs: Arguments supplémentaires

    Returns:
        RuleBasedSystem: Système de règles
    """
    config = {
        'conflict_resolution': conflict_resolution,
        'confidence_threshold': confidence_threshold,
        **kwargs
    }
    return RuleBasedSystem(config)


__all__ = [
    'RuleBasedSystem',
    'Rule',
    'RuleResult',
    'create_rule_system',
]

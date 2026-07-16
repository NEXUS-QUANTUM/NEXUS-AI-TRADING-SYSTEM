# ai/reasoning/logic_engine.py
"""
NEXUS AI TRADING SYSTEM - Logic Engine
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import re
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class LogicalExpression:
    """Expression logique"""
    operator: str
    operands: List[Any]
    negated: bool = False

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Évalue l'expression dans un contexte.

        Args:
            context: Contexte d'évaluation

        Returns:
            bool: Résultat de l'évaluation
        """
        if self.operator == 'and':
            result = all(op.evaluate(context) if isinstance(op, LogicalExpression) else self._evaluate_operand(op, context) for op in self.operands)
        elif self.operator == 'or':
            result = any(op.evaluate(context) if isinstance(op, LogicalExpression) else self._evaluate_operand(op, context) for op in self.operands)
        elif self.operator == 'not':
            result = not (self.operands[0].evaluate(context) if isinstance(self.operands[0], LogicalExpression) else self._evaluate_operand(self.operands[0], context))
        elif self.operator == 'gt':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left > right
        elif self.operator == 'lt':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left < right
        elif self.operator == 'eq':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left == right
        elif self.operator == 'gte':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left >= right
        elif self.operator == 'lte':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left <= right
        elif self.operator == 'neq':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left != right
        elif self.operator == 'contains':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = right in left
        elif self.operator == 'in':
            left = self._evaluate_operand(self.operands[0], context)
            right = self._evaluate_operand(self.operands[1], context)
            result = left in right
        else:
            raise ValueError(f"Opérateur non supporté: {self.operator}")

        return not result if self.negated else result

    def _evaluate_operand(self, operand: Any, context: Dict[str, Any]) -> Any:
        """Évalue un opérande"""
        if isinstance(operand, str) and operand.startswith('$'):
            # Référence à une variable du contexte
            key = operand[1:]
            return context.get(key, operand)
        return operand


@dataclass
class LogicalRule:
    """Règle logique"""
    name: str
    condition: LogicalExpression
    conclusion: Dict[str, Any]
    priority: int = 0
    weight: float = 1.0
    description: str = ""

    def evaluate(self, context: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Évalue la règle dans un contexte.

        Args:
            context: Contexte d'évaluation

        Returns:
            Tuple[bool, Dict[str, Any]]: (Condition satisfaite, Conclusions)
        """
        if self.condition.evaluate(context):
            return True, self.conclusion
        return False, {}


@dataclass
class LogicResult:
    """Résultat de logique"""
    conclusions: Dict[str, Any]
    rules_applied: List[str]
    confidence: float
    reasoning: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'conclusions': self.conclusions,
            'rules_applied': self.rules_applied,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat(),
        }


class LogicEngine:
    """
    Moteur logique pour l'IA de trading.

    Features:
    - Expressions logiques
    - Règles conditionnelles
    - Déduction logique
    - Gestion d'incertitude
    - Explications

    Example:
        ```python
        engine = LogicEngine()

        # Créer une règle
        condition = LogicalExpression(
            operator='and',
            operands=[
                LogicalExpression('gt', ['$rsi', 70]),
                LogicalExpression('lt', ['$volume', '$avg_volume'])
            ]
        )
        conclusion = {'signal': 'sell', 'reason': 'overbought_low_volume'}

        engine.add_rule('overbought', condition, conclusion)

        # Exécuter
        context = {'rsi': 75, 'volume': 100, 'avg_volume': 200}
        result = engine.execute(context)
        ```
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: List[LogicalRule] = []
        self.facts: Dict[str, Any] = {}
        self.results: List[LogicResult] = []

        # Configuration
        self.confidence_threshold = self.config.get('confidence_threshold', 0.5)
        self.max_rules = self.config.get('max_rules', 100)
        self.max_iterations = self.config.get('max_iterations', 10)

        logger.info(f"LogicEngine initialisé")

    def parse_expression(self, expr: Union[str, Dict, List]) -> LogicalExpression:
        """
        Parse une expression logique.

        Args:
            expr: Expression à parser

        Returns:
            LogicalExpression: Expression logique
        """
        if isinstance(expr, LogicalExpression):
            return expr

        if isinstance(expr, str):
            # Simple condition
            return LogicalExpression(operator='eq', operands=[expr, True])

        if isinstance(expr, dict):
            # Dictionnaire d'opérateurs
            for op, value in expr.items():
                if isinstance(value, list):
                    operands = [self.parse_expression(v) if isinstance(v, (dict, list)) else v for v in value]
                    return LogicalExpression(operator=op, operands=operands)

        if isinstance(expr, list):
            # Liste d'expressions
            return LogicalExpression(operator='and', operands=[self.parse_expression(e) for e in expr])

        return LogicalExpression(operator='eq', operands=[expr, True])

    def add_rule(
        self,
        name: str,
        condition: Union[Dict, List, LogicalExpression],
        conclusion: Dict[str, Any],
        priority: int = 0,
        weight: float = 1.0,
        description: str = ""
    ) -> None:
        """
        Ajoute une règle logique.

        Args:
            name: Nom de la règle
            condition: Condition logique
            conclusion: Conclusion
            priority: Priorité
            weight: Poids
            description: Description
        """
        if isinstance(condition, (dict, list)):
            condition = self.parse_expression(condition)

        rule = LogicalRule(
            name=name,
            condition=condition,
            conclusion=conclusion,
            priority=priority,
            weight=weight,
            description=description
        )

        self.rules.append(rule)
        self.rules.sort(key=lambda x: -x.priority)

        logger.info(f"Règle ajoutée: {name}")

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
        """Ajoute un fait"""
        self.facts[key] = value

    def add_facts(self, facts: Dict[str, Any]) -> None:
        """Ajoute plusieurs faits"""
        self.facts.update(facts)

    def execute(self, context: Dict[str, Any]) -> LogicResult:
        """
        Exécute le moteur logique.

        Args:
            context: Contexte d'entrée

        Returns:
            LogicResult: Résultat de l'exécution
        """
        # Fusion des faits et du contexte
        ctx = self.facts.copy()
        ctx.update(context)

        conclusions = {}
        applied_rules = []
        reasoning = []

        iteration = 0
        changed = True

        while changed and iteration < self.max_iterations:
            changed = False
            new_conclusions = {}

            # Évaluation des règles
            for rule in self.rules:
                try:
                    satisfied, rule_conclusion = rule.evaluate(ctx)

                    if satisfied:
                        # Vérification des conclusions dupliquées
                        for key, value in rule_conclusion.items():
                            if key not in conclusions or conclusions[key] != value:
                                new_conclusions[key] = value
                                applied_rules.append(rule.name)
                                reasoning.append(f"Règle '{rule.name}' déclenchée: {key} = {value}")
                                changed = True

                except Exception as e:
                    logger.warning(f"Erreur dans la règle {rule.name}: {e}")
                    reasoning.append(f"Erreur dans la règle '{rule.name}': {e}")

            # Mise à jour du contexte
            if new_conclusions:
                ctx.update(new_conclusions)
                conclusions.update(new_conclusions)

            iteration += 1

        # Calcul de la confiance
        confidence = self._compute_confidence(conclusions, applied_rules)

        result = LogicResult(
            conclusions=conclusions,
            rules_applied=applied_rules,
            confidence=confidence,
            reasoning=reasoning,
        )

        self.results.append(result)

        logger.info(f"Exécution terminée: {len(conclusions)} conclusions, {len(applied_rules)} règles")

        return result

    def _compute_confidence(self, conclusions: Dict[str, Any], applied_rules: List[str]) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            conclusions: Conclusions
            applied_rules: Règles appliquées

        Returns:
            float: Niveau de confiance
        """
        if not conclusions:
            return 0.0

        # Confiance basée sur le ratio de règles appliquées
        if self.rules:
            rule_ratio = len(applied_rules) / len(self.rules)
        else:
            rule_ratio = 0.5

        # Nombre de faits utilisés
        fact_ratio = min(1.0, len(self.facts) / 10) if self.facts else 0.5

        confidence = 0.6 * rule_ratio + 0.4 * fact_ratio
        confidence = min(1.0, confidence)

        return confidence

    def explain(self, result: LogicResult) -> str:
        """
        Génère une explication détaillée.

        Args:
            result: Résultat logique

        Returns:
            str: Explication
        """
        lines = [
            "=" * 60,
            "EXPLICATION LOGIQUE",
            "=" * 60,
            f"Timestamp: {result.timestamp}",
            f"Confiance: {result.confidence:.2f}",
            "-" * 60,
            "CONCLUSIONS:",
        ]

        for key, value in result.conclusions.items():
            lines.append(f"  {key} = {value}")

        lines.append("-" * 60)
        lines.append("RAISONNEMENT:")

        for step in result.reasoning:
            lines.append(f"  - {step}")

        lines.append("-" * 60)
        lines.append(f"Règles appliquées: {len(result.rules_applied)}")

        return "\n".join(lines)

    def get_rules(self) -> List[Dict[str, Any]]:
        """
        Retourne les règles.

        Returns:
            List[Dict[str, Any]]: Liste des règles
        """
        return [
            {
                'name': r.name,
                'priority': r.priority,
                'weight': r.weight,
                'description': r.description,
            }
            for r in self.rules
        ]

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le moteur logique.

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
                        'condition': r.condition,
                        'conclusion': r.conclusion,
                        'priority': r.priority,
                        'weight': r.weight,
                        'description': r.description,
                    }
                    for r in self.rules
                ],
                'facts': self.facts,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Moteur logique sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'LogicEngine':
        """
        Charge un moteur logique.

        Args:
            filepath: Chemin du fichier

        Returns:
            LogicEngine: Moteur logique chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            engine = cls(data.get('config', {}))

            # Restaurer les règles
            for rule_data in data.get('rules', []):
                engine.add_rule(
                    name=rule_data['name'],
                    condition=rule_data['condition'],
                    conclusion=rule_data['conclusion'],
                    priority=rule_data.get('priority', 0),
                    weight=rule_data.get('weight', 1.0),
                    description=rule_data.get('description', ''),
                )

            engine.facts = data.get('facts', {})

            logger.info(f"Moteur logique chargé: {filepath}")
            return engine

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_logic_engine(
    confidence_threshold: float = 0.5,
    max_rules: int = 100,
    **kwargs
) -> LogicEngine:
    """
    Factory pour créer un moteur logique.

    Args:
        confidence_threshold: Seuil de confiance
        max_rules: Nombre maximum de règles
        **kwargs: Arguments supplémentaires

    Returns:
        LogicEngine: Moteur logique
    """
    config = {
        'confidence_threshold': confidence_threshold,
        'max_rules': max_rules,
        **kwargs
    }
    return LogicEngine(config)


__all__ = [
    'LogicEngine',
    'LogicalExpression',
    'LogicalRule',
    'LogicResult',
    'create_logic_engine',
]

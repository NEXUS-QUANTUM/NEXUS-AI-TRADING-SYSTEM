# ai/models/ensemble/weighting_strategies.py
"""
NEXUS AI TRADING SYSTEM - Ensemble Weighting Strategies
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import List, Optional, Dict, Any, Callable, Union
from dataclasses import dataclass
from scipy.optimize import minimize
from scipy.special import softmax
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, log_loss
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class WeightingResult:
    weights: np.ndarray
    method: str
    scores: Optional[List[float]] = None
    performance: Optional[Dict[str, float]] = None
    convergence: bool = True
    iterations: int = 0


class WeightingStrategy:
    """Classe de base pour les stratégies de pondération des ensembles"""
    
    def __init__(self, name: str = "base"):
        self.name = name
        self.weights: Optional[np.ndarray] = None
    
    def compute_weights(self, model_scores: List[float], **kwargs) -> np.ndarray:
        raise NotImplementedError
    
    def get_params(self) -> Dict[str, Any]:
        return {'name': self.name}
    
    def __str__(self) -> str:
        return f"WeightingStrategy({self.name})"


class EqualWeighting(WeightingStrategy):
    """Pondération égale pour tous les modèles"""
    
    def __init__(self):
        super().__init__("equal")
    
    def compute_weights(self, model_scores: List[float], **kwargs) -> np.ndarray:
        n_models = len(model_scores)
        weights = np.ones(n_models) / n_models
        self.weights = weights
        return weights


class PerformanceWeighting(WeightingStrategy):
    """Pondération basée sur les performances des modèles"""
    
    def __init__(self, metric: str = 'r2', use_softmax: bool = True, temperature: float = 1.0):
        super().__init__("performance")
        self.metric = metric
        self.use_softmax = use_softmax
        self.temperature = temperature
    
    def compute_weights(self, model_scores: List[float], **kwargs) -> np.ndarray:
        scores = np.array(model_scores)
        scores = np.maximum(scores, 0.01)
        
        if self.use_softmax:
            weights = softmax(scores / self.temperature)
        else:
            weights = scores / scores.sum()
        
        self.weights = weights
        return weights


class RankWeighting(WeightingStrategy):
    """Pondération basée sur les rangs des modèles"""
    
    def __init__(self, decay: float = 1.0, use_exponential: bool = True):
        super().__init__("rank")
        self.decay = decay
        self.use_exponential = use_exponential
    
    def compute_weights(self, model_scores: List[float], **kwargs) -> np.ndarray:
        ranks = np.argsort(np.argsort(-np.array(model_scores))) + 1
        
        if self.use_exponential:
            weights = np.exp(-self.decay * ranks)
        else:
            weights = 1 / (ranks ** self.decay)
        
        weights = weights / weights.sum()
        self.weights = weights
        return weights


class ErrorWeighting(WeightingStrategy):
    """Pondération inverse basée sur l'erreur (moins d'erreur = plus de poids)"""
    
    def __init__(self, error_metric: str = 'mse', use_softmax: bool = True, epsilon: float = 1e-6):
        super().__init__("error")
        self.error_metric = error_metric
        self.use_softmax = use_softmax
        self.epsilon = epsilon
    
    def compute_weights(self, model_scores: List[float], model_errors: Optional[List[float]] = None, **kwargs) -> np.ndarray:
        if model_errors is not None:
            errors = np.array(model_errors)
            errors = np.maximum(errors, self.epsilon)
            inverse_errors = 1 / errors
        else:
            scores = np.array(model_scores)
            scores = np.maximum(scores, self.epsilon)
            inverse_errors = scores
        
        if self.use_softmax:
            weights = softmax(inverse_errors)
        else:
            weights = inverse_errors / inverse_errors.sum()
        
        self.weights = weights
        return weights


class CorrelationWeighting(WeightingStrategy):
    """Pondération basée sur la corrélation entre les modèles"""
    
    def __init__(self, diversity_weight: float = 0.5):
        super().__init__("correlation")
        self.diversity_weight = diversity_weight
    
    def compute_weights(self, model_scores: List[float], predictions: Optional[List[np.ndarray]] = None, **kwargs) -> np.ndarray:
        if predictions is None:
            logger.warning("Prédictions non fournies, utilisation des scores")
            return PerformanceWeighting().compute_weights(model_scores)
        
        n_models = len(predictions)
        correlation_matrix = np.zeros((n_models, n_models))
        
        for i in range(n_models):
            for j in range(n_models):
                if i != j:
                    corr = np.corrcoef(predictions[i], predictions[j])[0, 1]
                    correlation_matrix[i, j] = abs(corr)
        
        scores = np.array(model_scores)
        diversity_scores = 1 - np.mean(correlation_matrix, axis=1)
        
        combined_score = (1 - self.diversity_weight) * scores + self.diversity_weight * diversity_scores
        combined_score = np.maximum(combined_score, 0.01)
        
        weights = combined_score / combined_score.sum()
        self.weights = weights
        return weights


class SharpeWeighting(WeightingStrategy):
    """Pondération optimisée pour maximiser le ratio de Sharpe"""
    
    def __init__(self, risk_free_rate: float = 0.0):
        super().__init__("sharpe")
        self.risk_free_rate = risk_free_rate
    
    def compute_weights(self, model_scores: List[float], returns: Optional[np.ndarray] = None, **kwargs) -> np.ndarray:
        if returns is None:
            logger.warning("Returns non fournies, utilisation des scores")
            return PerformanceWeighting().compute_weights(model_scores)
        
        n_models = returns.shape[1] if len(returns.shape) > 1 else 1
        
        if n_models == 1:
            return np.array([1.0])
        
        def negative_sharpe(weights):
            weights = np.array(weights)
            weights = weights / weights.sum()
            portfolio_return = np.sum(returns.mean(axis=0) * weights)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(np.cov(returns.T), weights)))
            sharpe = (portfolio_return - self.risk_free_rate) / (portfolio_std + 1e-6)
            return -sharpe
        
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = [(0.0, 1.0) for _ in range(n_models)]
        initial_weights = np.ones(n_models) / n_models
        
        result = minimize(
            negative_sharpe,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        weights = result.x / result.x.sum()
        self.weights = weights
        return weights


class BayesianWeighting(WeightingStrategy):
    """Pondération bayésienne avec prior uniforme"""
    
    def __init__(self, prior_strength: float = 1.0, use_kl_divergence: bool = True):
        super().__init__("bayesian")
        self.prior_strength = prior_strength
        self.use_kl_divergence = use_kl_divergence
    
    def compute_weights(self, model_scores: List[float], model_uncertainties: Optional[List[float]] = None, **kwargs) -> np.ndarray:
        scores = np.array(model_scores)
        
        if model_uncertainties is not None:
            uncertainties = np.array(model_uncertainties)
            precision = 1 / (uncertainties + 1e-6)
            posterior = scores * precision
        else:
            if self.use_kl_divergence:
                scores = np.maximum(scores, 0.01)
                posterior = np.log(scores + 1)
            else:
                posterior = scores
        
        posterior = np.maximum(posterior, 0.01)
        weights = posterior / posterior.sum()
        self.weights = weights
        return weights


class DiversityWeighting(WeightingStrategy):
    """Pondération pour maximiser la diversité entre les modèles"""
    
    def __init__(self):
        super().__init__("diversity")
    
    def compute_weights(self, model_scores: List[float], predictions: Optional[List[np.ndarray]] = None, **kwargs) -> np.ndarray:
        if predictions is None or len(predictions) < 2:
            logger.warning("Prédictions non fournies ou insuffisantes, utilisation des scores")
            return PerformanceWeighting().compute_weights(model_scores)
        
        n_models = len(predictions)
        diversity_matrix = np.zeros((n_models, n_models))
        
        for i in range(n_models):
            for j in range(n_models):
                if i != j:
                    corr = np.corrcoef(predictions[i], predictions[j])[0, 1]
                    diversity_matrix[i, j] = 1 - abs(corr)
        
        diversity_scores = np.mean(diversity_matrix, axis=1)
        scores = np.array(model_scores)
        
        combined = diversity_scores * scores
        combined = np.maximum(combined, 0.01)
        
        weights = combined / combined.sum()
        self.weights = weights
        return weights


class OnlineWeighting(WeightingStrategy):
    """Pondération adaptative en ligne avec historique"""
    
    def __init__(self, learning_rate: float = 0.1, window_size: int = 100):
        super().__init__("online")
        self.learning_rate = learning_rate
        self.window_size = window_size
        self.history: List[Dict[str, Any]] = []
    
    def compute_weights(self, model_scores: List[float], **kwargs) -> np.ndarray:
        if not self.history:
            weights = np.ones(len(model_scores)) / len(model_scores)
        else:
            recent = self.history[-self.window_size:]
            performance = np.array([h['scores'] for h in recent])
            
            if len(recent) > 0:
                avg_performance = np.mean(performance, axis=0)
                weights = avg_performance / avg_performance.sum()
            else:
                weights = np.ones(len(model_scores)) / len(model_scores)
        
        self.weights = weights
        return weights
    
    def update(self, model_scores: List[float], predictions: List[np.ndarray], targets: np.ndarray):
        """Met à jour l'historique avec les nouvelles performances"""
        self.history.append({
            'scores': model_scores,
            'predictions': predictions,
            'targets': targets
        })


class EnsembleWeightingOptimizer:
    """
    Optimiseur pour les stratégies de pondération des ensembles.
    """
    
    def __init__(
        self,
        strategy: Optional[WeightingStrategy] = None,
        strategies: Optional[List[WeightingStrategy]] = None,
        validation_data: Optional[Dict[str, Any]] = None
    ):
        self.strategy = strategy
        self.strategies = strategies
        self.validation_data = validation_data
        self.best_strategy: Optional[WeightingStrategy] = None
        self.best_weights: Optional[np.ndarray] = None
        self.best_score: float = -float('inf')
        self.results: List[Dict[str, Any]] = []
    
    def optimize(self, model_scores: List[float], predictions: List[np.ndarray], targets: np.ndarray) -> WeightingResult:
        """Optimise la pondération en testant plusieurs stratégies"""
        
        if self.strategy is not None:
            weights = self.strategy.compute_weights(
                model_scores,
                predictions=predictions
            )
            score = self._evaluate_weights(weights, predictions, targets)
            
            return WeightingResult(
                weights=weights,
                method=self.strategy.name,
                performance={'score': score}
            )
        
        if self.strategies is None:
            self.strategies = self._get_default_strategies()
        
        best_score = -float('inf')
        best_weights = None
        best_method = None
        best_performance = None
        
        for strategy in self.strategies:
            try:
                weights = strategy.compute_weights(
                    model_scores,
                    predictions=predictions
                )
                score = self._evaluate_weights(weights, predictions, targets)
                
                self.results.append({
                    'strategy': strategy.name,
                    'weights': weights,
                    'score': score
                })
                
                if score > best_score:
                    best_score = score
                    best_weights = weights
                    best_method = strategy.name
                    best_performance = {'score': score}
                    self.best_strategy = strategy
                    
            except Exception as e:
                logger.error(f"Erreur pour la stratégie {strategy.name}: {e}")
                continue
        
        self.best_weights = best_weights
        self.best_score = best_score
        
        return WeightingResult(
            weights=best_weights,
            method=best_method,
            performance=best_performance
        )
    
    def _evaluate_weights(self, weights: np.ndarray, predictions: List[np.ndarray], targets: np.ndarray) -> float:
        """Évalue la performance d'une pondération"""
        weights_norm = weights / weights.sum()
        combined_pred = np.zeros_like(predictions[0])
        
        for i, pred in enumerate(predictions):
            combined_pred += weights_norm[i] * pred
        
        if SKLEARN_AVAILABLE:
            if len(np.unique(targets)) > 2:
                return r2_score(targets, combined_pred)
            else:
                return accuracy_score(targets, np.round(combined_pred))
        else:
            return -np.mean((targets - combined_pred) ** 2)
    
    def _get_default_strategies(self) -> List[WeightingStrategy]:
        """Retourne les stratégies par défaut"""
        return [
            EqualWeighting(),
            PerformanceWeighting(use_softmax=False),
            PerformanceWeighting(use_softmax=True, temperature=0.5),
            PerformanceWeighting(use_softmax=True, temperature=2.0),
            RankWeighting(decay=0.5),
            RankWeighting(decay=1.0),
            RankWeighting(decay=2.0),
            ErrorWeighting(use_softmax=False),
            ErrorWeighting(use_softmax=True),
            DiversityWeighting(),
            CorrelationWeighting(diversity_weight=0.3),
            CorrelationWeighting(diversity_weight=0.7),
            BayesianWeighting(prior_strength=0.5),
            BayesianWeighting(prior_strength=2.0),
        ]
    
    def get_best_strategy(self) -> Optional[WeightingStrategy]:
        """Retourne la meilleure stratégie trouvée"""
        return self.best_strategy
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Retourne tous les résultats de l'optimisation"""
        return self.results


def create_weighting_strategy(
    method: str = 'performance',
    **kwargs
) -> WeightingStrategy:
    """Factory pour créer des stratégies de pondération"""
    
    strategies = {
        'equal': EqualWeighting,
        'performance': PerformanceWeighting,
        'rank': RankWeighting,
        'error': ErrorWeighting,
        'correlation': CorrelationWeighting,
        'sharpe': SharpeWeighting,
        'bayesian': BayesianWeighting,
        'diversity': DiversityWeighting,
        'online': OnlineWeighting,
    }
    
    strategy_class = strategies.get(method.lower())
    if strategy_class is None:
        raise ValueError(f"Stratégie non supportée: {method}")
    
    return strategy_class(**kwargs)


__all__ = [
    'WeightingStrategy',
    'EqualWeighting',
    'PerformanceWeighting',
    'RankWeighting',
    'ErrorWeighting',
    'CorrelationWeighting',
    'SharpeWeighting',
    'BayesianWeighting',
    'DiversityWeighting',
    'OnlineWeighting',
    'EnsembleWeightingOptimizer',
    'WeightingResult',
    'create_weighting_strategy',
]

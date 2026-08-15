"""
Swing Bot Bayesian Model
==========================

This module provides Bayesian analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from scipy import stats
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class BayesianPrior:
    """Bayesian prior distribution."""
    distribution: str  # 'normal', 'beta', 'gamma', 'uniform'
    parameters: Dict[str, float]
    weight: float = 1.0


@dataclass
class BayesianPosterior:
    """Bayesian posterior distribution."""
    distribution: str
    parameters: Dict[str, float]
    credible_interval: Tuple[float, float]
    mean: float
    std: float
    timestamp: datetime


@dataclass
class BayesianSignal:
    """Bayesian trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    probability: float
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    posterior: BayesianPosterior
    indicators: Dict[str, Any] = field(default_factory=dict)


class BayesianModel:
    """
    Bayesian analysis model for trading decisions.
    
    Implements Bayesian inference for probability estimation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Bayesian model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.priors: Dict[str, BayesianPrior] = {}
        self.posteriors: Dict[str, List[BayesianPosterior]] = {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.credible_interval = self.config.get('credible_interval', 0.95)
        
        # Register default priors
        self._register_default_priors()
        
    def _register_default_priors(self) -> None:
        """Register default prior distributions."""
        self.priors['price_return'] = BayesianPrior(
            distribution='normal',
            parameters={'mean': 0.0, 'std': 0.02},
            weight=1.0
        )
        
        self.priors['volatility'] = BayesianPrior(
            distribution='gamma',
            parameters={'shape': 2.0, 'scale': 0.5},
            weight=1.0
        )
        
        self.priors['win_rate'] = BayesianPrior(
            distribution='beta',
            parameters={'alpha': 10.0, 'beta': 10.0},
            weight=1.0
        )
    
    def update_posterior(self, data: np.ndarray, variable: str) -> BayesianPosterior:
        """
        Update posterior distribution with new data.
        
        Args:
            data: New data
            variable: Variable name
            
        Returns:
            BayesianPosterior object
        """
        if variable not in self.priors:
            raise ValueError(f"Unknown variable: {variable}")
        
        prior = self.priors[variable]
        
        if prior.distribution == 'normal':
            posterior = self._update_normal_posterior(data, prior)
        elif prior.distribution == 'beta':
            posterior = self._update_beta_posterior(data, prior)
        elif prior.distribution == 'gamma':
            posterior = self._update_gamma_posterior(data, prior)
        else:
            raise ValueError(f"Unsupported distribution: {prior.distribution}")
        
        # Store posterior
        if variable not in self.posteriors:
            self.posteriors[variable] = []
        self.posteriors[variable].append(posterior)
        
        return posterior
    
    def _update_normal_posterior(self, data: np.ndarray, prior: BayesianPrior) -> BayesianPosterior:
        """
        Update normal posterior distribution.
        
        Args:
            data: New data
            prior: Prior distribution
            
        Returns:
            BayesianPosterior object
        """
        # Prior parameters
        prior_mean = prior.parameters.get('mean', 0)
        prior_std = prior.parameters.get('std', 1)
        
        # Data parameters
        data_mean = np.mean(data) if len(data) > 0 else 0
        data_std = np.std(data) if len(data) > 0 else 1
        n = len(data)
        
        # Posterior parameters
        posterior_var = 1 / (1 / (prior_std ** 2) + n / (data_std ** 2))
        posterior_mean = posterior_var * (prior_mean / (prior_std ** 2) + n * data_mean / (data_std ** 2))
        posterior_std = np.sqrt(posterior_var)
        
        # Credible interval
        z_score = stats.norm.ppf(1 - (1 - self.credible_interval) / 2)
        lower = posterior_mean - z_score * posterior_std
        upper = posterior_mean + z_score * posterior_std
        
        return BayesianPosterior(
            distribution='normal',
            parameters={'mean': posterior_mean, 'std': posterior_std},
            credible_interval=(lower, upper),
            mean=posterior_mean,
            std=posterior_std,
            timestamp=datetime.now()
        )
    
    def _update_beta_posterior(self, data: np.ndarray, prior: BayesianPrior) -> BayesianPosterior:
        """
        Update beta posterior distribution.
        
        Args:
            data: New data
            prior: Prior distribution
            
        Returns:
            BayesianPosterior object
        """
        # Prior parameters
        alpha0 = prior.parameters.get('alpha', 1)
        beta0 = prior.parameters.get('beta', 1)
        
        # Count successes and failures
        successes = np.sum(data) if len(data) > 0 else 0
        failures = len(data) - successes
        
        # Posterior parameters
        alpha = alpha0 + successes
        beta = beta0 + failures
        
        # Calculate mean and std
        mean = alpha / (alpha + beta)
        std = np.sqrt(alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1)))
        
        # Credible interval
        lower = stats.beta.ppf((1 - self.credible_interval) / 2, alpha, beta)
        upper = stats.beta.ppf((1 + self.credible_interval) / 2, alpha, beta)
        
        return BayesianPosterior(
            distribution='beta',
            parameters={'alpha': alpha, 'beta': beta},
            credible_interval=(lower, upper),
            mean=mean,
            std=std,
            timestamp=datetime.now()
        )
    
    def _update_gamma_posterior(self, data: np.ndarray, prior: BayesianPrior) -> BayesianPosterior:
        """
        Update gamma posterior distribution.
        
        Args:
            data: New data
            prior: Prior distribution
            
        Returns:
            BayesianPosterior object
        """
        # Prior parameters
        shape0 = prior.parameters.get('shape', 1)
        scale0 = prior.parameters.get('scale', 1)
        
        # Data parameters
        n = len(data)
        sum_data = np.sum(data) if len(data) > 0 else 0
        
        # Posterior parameters
        shape = shape0 + n
        scale = scale0 + sum_data
        
        # Calculate mean and std
        mean = shape * scale
        std = np.sqrt(shape) * scale
        
        # Credible interval
        lower = stats.gamma.ppf((1 - self.credible_interval) / 2, shape, scale=scale)
        upper = stats.gamma.ppf((1 + self.credible_interval) / 2, shape, scale=scale)
        
        return BayesianPosterior(
            distribution='gamma',
            parameters={'shape': shape, 'scale': scale},
            credible_interval=(lower, upper),
            mean=mean,
            std=std,
            timestamp=datetime.now()
        )
    
    def predict_probability(self, variable: str, value: float) -> float:
        """
        Predict probability of a value using posterior distribution.
        
        Args:
            variable: Variable name
            value: Value to predict
            
        Returns:
            Probability of the value
        """
        if variable not in self.posteriors or not self.posteriors[variable]:
            return 0.5
        
        posterior = self.posteriors[variable][-1]
        
        if posterior.distribution == 'normal':
            prob = stats.norm.pdf(value, posterior.mean, posterior.std)
            return min(prob * 10, 1.0)  # Scale probability
        elif posterior.distribution == 'beta':
            prob = stats.beta.pdf(value, posterior.parameters['alpha'], 
                                posterior.parameters['beta'])
            return min(prob * 5, 1.0)
        elif posterior.distribution == 'gamma':
            prob = stats.gamma.pdf(value, posterior.parameters['shape'],
                                 scale=posterior.parameters['scale'])
            return min(prob * 5, 1.0)
        
        return 0.5
    
    def calculate_probability(self, data: np.ndarray, variable: str) -> float:
        """
        Calculate probability using Bayesian inference.
        
        Args:
            data: New data
            variable: Variable name
            
        Returns:
            Probability value
        """
        # Update posterior
        posterior = self.update_posterior(data, variable)
        
        # Calculate probability of positive outcome
        if posterior.distribution == 'normal':
            prob = 1 - stats.norm.cdf(0, posterior.mean, posterior.std)
        elif posterior.distribution == 'beta':
            prob = 1 - stats.beta.cdf(0.5, posterior.parameters['alpha'],
                                    posterior.parameters['beta'])
        elif posterior.distribution == 'gamma':
            prob = 1 - stats.gamma.cdf(1, posterior.parameters['shape'],
                                     scale=posterior.parameters['scale'])
        else:
            prob = 0.5
        
        return min(max(prob, 0.0), 1.0)
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[BayesianSignal]:
        """
        Generate trading signal based on Bayesian inference.
        
        Args:
            df: OHLCV data
            
        Returns:
            BayesianSignal or None
        """
        if len(df) < self.lookback_period:
            return None
        
        # Calculate returns
        returns = df['close'].pct_change().dropna()
        
        # Update posteriors
        returns_posterior = self.update_posterior(returns.values, 'price_return')
        
        # Calculate probabilities
        prob_up = self.predict_probability('price_return', 0.01)
        prob_down = self.predict_probability('price_return', -0.01)
        
        # Calculate confidence
        confidence = max(prob_up, prob_down)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Generate signal
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        if prob_up > prob_down:
            signal_type = 'buy'
            reason = f"Bayesian probability of upward movement: {prob_up:.2%}"
            target = current_price * (1 + confidence * 0.5)
            stop_loss = current_price * (1 - confidence * 0.25)
        else:
            signal_type = 'sell'
            reason = f"Bayesian probability of downward movement: {prob_down:.2%}"
            target = current_price * (1 - confidence * 0.5)
            stop_loss = current_price * (1 + confidence * 0.25)
        
        return BayesianSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            probability=max(prob_up, prob_down),
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            posterior=returns_posterior,
            indicators={
                'prob_up': prob_up,
                'prob_down': prob_down,
                'credible_interval': returns_posterior.credible_interval
            }
        )
    
    def get_bayesian_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get Bayesian statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Bayesian statistics
        """
        if len(df) < self.lookback_period:
            return {'status': 'insufficient_data'}
        
        returns = df['close'].pct_change().dropna()
        posterior = self.update_posterior(returns.values, 'price_return')
        
        prob_up = self.predict_probability('price_return', 0.01)
        prob_down = self.predict_probability('price_return', -0.01)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'posterior': {
                'distribution': posterior.distribution,
                'mean': posterior.mean,
                'std': posterior.std,
                'credible_interval': posterior.credible_interval
            },
            'probabilities': {
                'up': prob_up,
                'down': prob_down,
                'neutral': 1 - prob_up - prob_down
            },
            'confidence': max(prob_up, prob_down),
            'signal_bias': 'bullish' if prob_up > prob_down else 'bearish',
            'posterior_history_length': len(self.posteriors.get('price_return', []))
        }


def create_bayesian_model(config: Optional[Dict[str, Any]] = None) -> BayesianModel:
    """
    Create a Bayesian model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        BayesianModel instance
    """
    return BayesianModel(config)


__all__ = [
    'BayesianPrior',
    'BayesianPosterior',
    'BayesianSignal',
    'BayesianModel',
    'create_bayesian_model'
]

"""
Swing Bot Models Package
==========================

This package contains all analytical models for the Swing Bot trading system.
Each model provides specific analysis capabilities for different trading strategies
and market conditions.

The models are organized by functionality:
- Statistical models (VAR, CVaR, Sortino, Sharpe, Calmar)
- Technical models (Momentum, Trend, Support/Resistance, Fibonacci)
- Market analysis models (Volatility, Volume, Liquidity, Market Cycle)
- Trading models (Mean Reversion, Breakout, Continuation, Reversal)
- Advanced models (Machine Learning, Deep Learning, Ensemble, Hybrid)
- Risk models (Drawdown, Exposure, Margin, Stress, Scenario)
"""

import warnings
warnings.filterwarnings('ignore')

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Import all model classes for easy access
from .accumulation import (
    AccumulationSignal,
    AccumulationMetrics,
    AccumulationModel,
    SmartMoneyModel,
    create_accumulation_model,
    create_smart_money_model
)

from .adaptation import (
    AdaptationState,
    LearningSample,
    AdaptationSignal,
    AdaptationModel,
    create_adaptation_model
)

from .adaptive import (
    AdaptiveState,
    AdaptiveSignal,
    AdaptiveModel,
    create_adaptive_model
)

from .asset_allocation import (
    AssetAllocation,
    AssetAllocationSignal,
    AssetAllocationModel,
    create_asset_allocation_model
)

from .basket_trading import (
    BasketTrade,
    BasketSignal,
    BasketTradingModel,
    create_basket_trading_model
)

from .bayesian import (
    BayesianPrior,
    BayesianPosterior,
    BayesianSignal,
    BayesianModel,
    create_bayesian_model
)

from .breadth import (
    BreadthIndicator,
    BreadthSignal,
    BreadthModel,
    create_breadth_model
)

from .breakout import (
    BreakoutPattern,
    BreakoutSignal,
    BreakoutModel,
    create_breakout_model
)

from .calmar import (
    CalmarMetrics,
    CalmarSignal,
    CalmarModel,
    create_calmar_model
)

from .channel import (
    ChannelPattern,
    ChannelSignal,
    ChannelModel,
    create_channel_model
)

from .chaos import (
    ChaosMetrics,
    ChaosSignal,
    ChaosModel,
    create_chaos_model
)

from .cognition import (
    CognitiveState,
    CognitiveSignal,
    CognitionModel,
    create_cognition_model
)

from .complexity import (
    ComplexityMetrics,
    ComplexitySignal,
    ComplexityModel,
    create_complexity_model
)

from .concentration import (
    ConcentrationMetrics,
    ConcentrationSignal,
    ConcentrationModel,
    create_concentration_model
)

from .consolidation import (
    ConsolidationPattern,
    ConsolidationSignal,
    ConsolidationModel,
    create_consolidation_model
)

from .continuation import (
    ContinuationPattern,
    ContinuationSignal,
    ContinuationModel,
    create_continuation_model
)

from .convergence import (
    ConvergenceMetrics,
    ConvergenceSignal,
    ConvergenceModel,
    create_convergence_model
)

from .correlation import (
    CorrelationMetrics,
    CorrelationSignal,
    CorrelationModel,
    create_correlation_model
)

from .cvar import (
    CVaRMetrics,
    CVaRSignal,
    CVaRModel,
    create_cvar_model
)

from .decision import (
    DecisionCriteria,
    DecisionResult,
    DecisionSignal,
    DecisionModel,
    create_decision_model
)

from .deep_learning import (
    DeepLearningConfig,
    DeepLearningPrediction,
    DeepLearningSignal,
    DeepLearningModel,
    create_deep_learning_model
)

from .distribution import (
    DistributionMetrics,
    DistributionSignal,
    DistributionModel,
    create_distribution_model
)

from .divergence import (
    DivergencePattern,
    DivergenceSignal,
    DivergenceModel,
    create_divergence_model
)

from .diversification import (
    DiversificationMetrics,
    DiversificationSignal,
    DiversificationModel,
    create_diversification_model
)

from .drawdown import (
    DrawdownMetrics,
    DrawdownSignal,
    DrawdownModel,
    create_drawdown_model
)

from .elliott_wave import (
    ElliottWave,
    WaveSignal,
    ElliottWaveModel,
    create_elliott_wave_model
)

from .ensemble import (
    EnsemblePrediction,
    EnsembleSignal,
    EnsembleModel,
    create_ensemble_model
)

from .entropy import (
    EntropyMetrics,
    EntropySignal,
    EntropyModel,
    create_entropy_model
)

from .evolution import (
    Individual,
    EvolutionResult,
    EvolutionSignal,
    EvolutionModel,
    create_evolution_model
)

from .evolutionary import (
    EvolutionaryStrategy,
    EvolutionaryResult,
    EvolutionarySignal,
    EvolutionaryModel,
    create_evolutionary_model
)

from .excellence import (
    ExcellenceMetric,
    ExcellenceReport,
    ExcellenceSignal,
    ExcellenceModel,
    create_excellence_model
)

from .execution import (
    ExecutionMetrics,
    ExecutionSignal,
    ExecutionModel,
    create_execution_model
)

from .exposure import (
    ExposureMetrics,
    ExposureSignal,
    ExposureModel,
    create_exposure_model
)

from .feedback import (
    FeedbackMetrics,
    FeedbackSignal,
    FeedbackModel,
    create_feedback_model
)

from .fibonacci import (
    FibonacciLevel,
    FibonacciSignal,
    FibonacciModel,
    create_fibonacci_model
)

from .flag import (
    FlagPattern,
    FlagSignal,
    FlagModel,
    create_flag_model
)

from .forecast import (
    ForecastResult,
    ForecastSignal,
    ForecastModel,
    create_forecast_model
)

from .fractal import (
    FractalMetrics,
    FractalSignal,
    FractalModel,
    create_fractal_model
)

from .fundamental import (
    FundamentalMetrics,
    FundamentalSignal,
    FundamentalModel,
    create_fundamental_model
)

from .fuzzy import (
    FuzzyMembership,
    FuzzyRule,
    FuzzyResult,
    FuzzySignal,
    FuzzyModel,
    create_fuzzy_model
)

from .genetic import (
    Chromosome,
    GeneticResult,
    GeneticSignal,
    GeneticModel,
    create_genetic_model
)

from .hurst import (
    HurstMetrics,
    HurstSignal,
    HurstModel,
    create_hurst_model
)

from .hybrid import (
    HybridModelConfig,
    HybridPrediction,
    HybridSignal,
    HybridModel,
    create_hybrid_model
)

from .improvement import (
    ImprovementMetric,
    ImprovementPlan,
    ImprovementSignal,
    ImprovementModel,
    create_improvement_model
)

from .industry import (
    IndustryMetrics,
    IndustrySignal,
    IndustryModel,
    create_industry_model
)

from .intelligence import (
    IntelligenceMetrics,
    IntelligenceSignal,
    IntelligenceModel,
    create_intelligence_model
)

from .learning import (
    LearningMetrics,
    LearningSignal,
    LearningModel,
    create_learning_model
)

from .leverage import (
    LeverageMetrics,
    LeverageSignal,
    LeverageModel,
    create_leverage_model
)

from .lyapunov import (
    LyapunovMetrics,
    LyapunovSignal,
    LyapunovModel,
    create_lyapunov_model
)

from .machine_learning import (
    MLPrediction,
    MLSignal,
    MachineLearningModel,
    create_machine_learning_model
)

from .macro import (
    MacroIndicator,
    MacroSignal,
    MacroModel,
    create_macro_model
)

from .margin import (
    MarginMetrics,
    MarginSignal,
    MarginModel,
    create_margin_model
)

from .market_cycle import (
    MarketCycle,
    CycleSignal,
    MarketCycleModel,
    create_market_cycle_model
)

from .mean_reversion import (
    MeanReversionMetrics,
    MeanReversionSignal,
    MeanReversionModel,
    create_mean_reversion_model
)

from .momentum import (
    MomentumMetrics,
    MomentumSignal,
    MomentumModel,
    create_momentum_model
)

from .monte_carlo import (
    MonteCarloResult,
    MonteCarloSignal,
    MonteCarloModel,
    create_monte_carlo_model
)

from .neuro import (
    NeuroNetwork,
    NeuroPrediction,
    NeuroSignal,
    NeuroModel,
    create_neuro_model
)

from .optimization import (
    OptimizationResult,
    OptimizationSignal,
    OptimizationModel,
    create_optimization_model
)

from .pair_trading import (
    Pair,
    PairTrade,
    PairSignal,
    PairTradingModel,
    create_pair_trading_model
)

from .pennant import (
    PennantPattern,
    PennantSignal,
    PennantModel,
    create_pennant_model
)

from .perception import (
    MarketPerception,
    PerceptionSignal,
    PerceptionModel,
    create_perception_model
)

from .planning import (
    TradingPlan,
    PlanningSignal,
    PlanningModel,
    create_planning_model
)

from .portfolio import (
    Position,
    PortfolioStats,
    PortfolioSignal,
    PortfolioModel,
    create_portfolio_model
)

from .predictive import (
    Prediction,
    PredictiveSignal,
    PredictiveModel,
    create_predictive_model
)

from .reasoning import (
    ReasoningRule,
    ReasoningResult,
    ReasoningSignal,
    ReasoningModel,
    create_reasoning_model
)

from .recommendation import (
    Recommendation,
    RecommendationSignal,
    RecommendationModel,
    create_recommendation_model
)

from .reinforcement_learning import (
    RLState,
    RLAction,
    RLExperience,
    RLSignal,
    ReinforcementLearningModel,
    create_reinforcement_learning_model
)

from .relative_strength import (
    RelativeStrengthMetrics,
    RelativeStrengthSignal,
    RelativeStrengthModel,
    create_relative_strength_model
)

from .retracement import (
    RetracementLevel,
    RetracementPattern,
    RetracementSignal,
    RetracementModel,
    create_retracement_model
)

from .reversal import (
    ReversalPattern,
    ReversalSignal,
    ReversalModel,
    create_reversal_model
)

from .reversion import (
    ReversionMetrics,
    ReversionSignal,
    ReversionModel,
    create_reversion_model
)

from .rotation import (
    RotationMetrics,
    RotationSignal,
    RotationModel,
    create_rotation_model
)

from .scenario import (
    Scenario,
    ScenarioResult,
    ScenarioSignal,
    ScenarioModel,
    create_scenario_model
)

from .sector import (
    SectorMetrics,
    SectorRotation,
    SectorSignal,
    SectorModel,
    create_sector_model
)

from .sentiment import (
    SentimentMetrics,
    SentimentSignal,
    SentimentModel,
    create_sentiment_model
)

from .sharpe import (
    SharpeMetrics,
    SharpeSignal,
    SharpeModel,
    create_sharpe_model
)

from .simulation import (
    SimulationScenario,
    MonteCarloResult as SimMonteCarloResult,
    SimulationSignal,
    SimulationModel,
    create_simulation_model
)

from .sortino import (
    SortinoMetrics,
    SortinoSignal,
    SortinoModel,
    create_sortino_model
)

from .statistical_arbitrage import (
    StatArbPair,
    StatArbTrade,
    StatArbSignal,
    StatisticalArbitrageModel,
    create_statistical_arbitrage_model
)

from .stress import (
    StressScenario,
    StressResult,
    StressSignal,
    StressModel,
    create_stress_model
)

from .support_resistance import (
    SupportResistanceLevel,
    SupportResistanceSignal,
    SupportResistanceModel,
    create_support_resistance_model
)

from .trend import (
    TrendIndicator,
    TrendAnalysis,
    TrendSignal,
    TrendModel,
    create_trend_model
)

from .trendline import (
    Trendline,
    TrendlineSignal,
    TrendlineModel,
    create_trendline_model
)

from .triangle import (
    TrianglePattern,
    TriangleSignal,
    TriangleModel,
    create_triangle_model
)

from .var import (
    VaRResult,
    VaRReport,
    VaRModel,
    create_var_model
)

from .volatility import (
    VolatilityIndicator,
    VolatilityRegime,
    VolatilitySignal,
    VolatilityModel,
    create_volatility_model
)

from .volume import (
    VolumeIndicator,
    VolumePattern,
    VolumeSignal,
    VolumeModel,
    create_volume_model
)

from .wavelet import (
    WaveletDecomposition,
    WaveletAnalysis,
    WaveletSignal,
    WaveletModel,
    create_wavelet_model
)

from .wedge import (
    WedgePattern,
    WedgeSignal,
    WedgeModel,
    create_wedge_model
)

from .wyckoff import (
    WyckoffPhase,
    WyckoffSignal,
    WyckoffModel,
    create_wyckoff_model
)


# Model registry - mapping of model names to their classes
MODEL_REGISTRY = {
    'accumulation': AccumulationModel,
    'adaptation': AdaptationModel,
    'adaptive': AdaptiveModel,
    'asset_allocation': AssetAllocationModel,
    'basket_trading': BasketTradingModel,
    'bayesian': BayesianModel,
    'breadth': BreadthModel,
    'breakout': BreakoutModel,
    'calmar': CalmarModel,
    'channel': ChannelModel,
    'chaos': ChaosModel,
    'cognition': CognitionModel,
    'complexity': ComplexityModel,
    'concentration': ConcentrationModel,
    'consolidation': ConsolidationModel,
    'continuation': ContinuationModel,
    'convergence': ConvergenceModel,
    'correlation': CorrelationModel,
    'cvar': CVaRModel,
    'decision': DecisionModel,
    'deep_learning': DeepLearningModel,
    'distribution': DistributionModel,
    'divergence': DivergenceModel,
    'diversification': DiversificationModel,
    'drawdown': DrawdownModel,
    'elliott_wave': ElliottWaveModel,
    'ensemble': EnsembleModel,
    'entropy': EntropyModel,
    'evolution': EvolutionModel,
    'evolutionary': EvolutionaryModel,
    'excellence': ExcellenceModel,
    'execution': ExecutionModel,
    'exposure': ExposureModel,
    'feedback': FeedbackModel,
    'fibonacci': FibonacciModel,
    'flag': FlagModel,
    'forecast': ForecastModel,
    'fractal': FractalModel,
    'fundamental': FundamentalModel,
    'fuzzy': FuzzyModel,
    'genetic': GeneticModel,
    'hurst': HurstModel,
    'hybrid': HybridModel,
    'improvement': ImprovementModel,
    'industry': IndustryModel,
    'intelligence': IntelligenceModel,
    'learning': LearningModel,
    'leverage': LeverageModel,
    'lyapunov': LyapunovModel,
    'machine_learning': MachineLearningModel,
    'macro': MacroModel,
    'margin': MarginModel,
    'market_cycle': MarketCycleModel,
    'mean_reversion': MeanReversionModel,
    'momentum': MomentumModel,
    'monte_carlo': MonteCarloModel,
    'neuro': NeuroModel,
    'optimization': OptimizationModel,
    'pair_trading': PairTradingModel,
    'pennant': PennantModel,
    'perception': PerceptionModel,
    'planning': PlanningModel,
    'portfolio': PortfolioModel,
    'predictive': PredictiveModel,
    'reasoning': ReasoningModel,
    'recommendation': RecommendationModel,
    'reinforcement_learning': ReinforcementLearningModel,
    'relative_strength': RelativeStrengthModel,
    'retracement': RetracementModel,
    'reversal': ReversalModel,
    'reversion': ReversionModel,
    'rotation': RotationModel,
    'scenario': ScenarioModel,
    'sector': SectorModel,
    'sentiment': SentimentModel,
    'sharpe': SharpeModel,
    'simulation': SimulationModel,
    'sortino': SortinoModel,
    'statistical_arbitrage': StatisticalArbitrageModel,
    'stress': StressModel,
    'support_resistance': SupportResistanceModel,
    'trend': TrendModel,
    'trendline': TrendlineModel,
    'triangle': TriangleModel,
    'var': VaRModel,
    'volatility': VolatilityModel,
    'volume': VolumeModel,
    'wavelet': WaveletModel,
    'wedge': WedgeModel,
    'wyckoff': WyckoffModel,
}


def get_model(model_name: str, config: Optional[Dict[str, Any]] = None):
    """
    Get a model instance by name.
    
    Args:
        model_name: Name of the model
        config: Configuration for the model
        
    Returns:
        Model instance
        
    Raises:
        ValueError: If model name is not found
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}")
    
    model_class = MODEL_REGISTRY[model_name]
    return model_class(config)


def get_all_model_names() -> List[str]:
    """
    Get list of all available model names.
    
    Returns:
        List of model names
    """
    return list(MODEL_REGISTRY.keys())


def get_model_info(model_name: str) -> Dict[str, Any]:
    """
    Get information about a model.
    
    Args:
        model_name: Name of the model
        
    Returns:
        Model information dictionary
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {model_name}")
    
    model_class = MODEL_REGISTRY[model_name]
    return {
        'name': model_name,
        'class': model_class.__name__,
        'module': model_class.__module__,
        'doc': model_class.__doc__
    }


# Export all public classes and functions
__all__ = [
    # Model classes
    'AccumulationSignal', 'AccumulationMetrics', 'AccumulationModel', 'SmartMoneyModel',
    'AdaptationState', 'LearningSample', 'AdaptationSignal', 'AdaptationModel',
    'AdaptiveState', 'AdaptiveSignal', 'AdaptiveModel',
    'AssetAllocation', 'AssetAllocationSignal', 'AssetAllocationModel',
    'BasketTrade', 'BasketSignal', 'BasketTradingModel',
    'BayesianPrior', 'BayesianPosterior', 'BayesianSignal', 'BayesianModel',
    'BreadthIndicator', 'BreadthSignal', 'BreadthModel',
    'BreakoutPattern', 'BreakoutSignal', 'BreakoutModel',
    'CalmarMetrics', 'CalmarSignal', 'CalmarModel',
    'ChannelPattern', 'ChannelSignal', 'ChannelModel',
    'ChaosMetrics', 'ChaosSignal', 'ChaosModel',
    'CognitiveState', 'CognitiveSignal', 'CognitionModel',
    'ComplexityMetrics', 'ComplexitySignal', 'ComplexityModel',
    'ConcentrationMetrics', 'ConcentrationSignal', 'ConcentrationModel',
    'ConsolidationPattern', 'ConsolidationSignal', 'ConsolidationModel',
    'ContinuationPattern', 'ContinuationSignal', 'ContinuationModel',
    'ConvergenceMetrics', 'ConvergenceSignal', 'ConvergenceModel',
    'CorrelationMetrics', 'CorrelationSignal', 'CorrelationModel',
    'CVaRMetrics', 'CVaRSignal', 'CVaRModel',
    'DecisionCriteria', 'DecisionResult', 'DecisionSignal', 'DecisionModel',
    'DeepLearningConfig', 'DeepLearningPrediction', 'DeepLearningSignal', 'DeepLearningModel',
    'DistributionMetrics', 'DistributionSignal', 'DistributionModel',
    'DivergencePattern', 'DivergenceSignal', 'DivergenceModel',
    'DiversificationMetrics', 'DiversificationSignal', 'DiversificationModel',
    'DrawdownMetrics', 'DrawdownSignal', 'DrawdownModel',
    'ElliottWave', 'WaveSignal', 'ElliottWaveModel',
    'EnsemblePrediction', 'EnsembleSignal', 'EnsembleModel',
    'EntropyMetrics', 'EntropySignal', 'EntropyModel',
    'Individual', 'EvolutionResult', 'EvolutionSignal', 'EvolutionModel',
    'EvolutionaryStrategy', 'EvolutionaryResult', 'EvolutionarySignal', 'EvolutionaryModel',
    'ExcellenceMetric', 'ExcellenceReport', 'ExcellenceSignal', 'ExcellenceModel',
    'ExecutionMetrics', 'ExecutionSignal', 'ExecutionModel',
    'ExposureMetrics', 'ExposureSignal', 'ExposureModel',
    'FeedbackMetrics', 'FeedbackSignal', 'FeedbackModel',
    'FibonacciLevel', 'FibonacciSignal', 'FibonacciModel',
    'FlagPattern', 'FlagSignal', 'FlagModel',
    'ForecastResult', 'ForecastSignal', 'ForecastModel',
    'FractalMetrics', 'FractalSignal', 'FractalModel',
    'FundamentalMetrics', 'FundamentalSignal', 'FundamentalModel',
    'FuzzyMembership', 'FuzzyRule', 'FuzzyResult', 'FuzzySignal', 'FuzzyModel',
    'Chromosome', 'GeneticResult', 'GeneticSignal', 'GeneticModel',
    'HurstMetrics', 'HurstSignal', 'HurstModel',
    'HybridModelConfig', 'HybridPrediction', 'HybridSignal', 'HybridModel',
    'ImprovementMetric', 'ImprovementPlan', 'ImprovementSignal', 'ImprovementModel',
    'IndustryMetrics', 'IndustrySignal', 'IndustryModel',
    'IntelligenceMetrics', 'IntelligenceSignal', 'IntelligenceModel',
    'LearningMetrics', 'LearningSignal', 'LearningModel',
    'LeverageMetrics', 'LeverageSignal', 'LeverageModel',
    'LyapunovMetrics', 'LyapunovSignal', 'LyapunovModel',
    'MLPrediction', 'MLSignal', 'MachineLearningModel',
    'MacroIndicator', 'MacroSignal', 'MacroModel',
    'MarginMetrics', 'MarginSignal', 'MarginModel',
    'MarketCycle', 'CycleSignal', 'MarketCycleModel',
    'MeanReversionMetrics', 'MeanReversionSignal', 'MeanReversionModel',
    'MomentumMetrics', 'MomentumSignal', 'MomentumModel',
    'MonteCarloResult', 'MonteCarloSignal', 'MonteCarloModel',
    'NeuroNetwork', 'NeuroPrediction', 'NeuroSignal', 'NeuroModel',
    'OptimizationResult', 'OptimizationSignal', 'OptimizationModel',
    'Pair', 'PairTrade', 'PairSignal', 'PairTradingModel',
    'PennantPattern', 'PennantSignal', 'PennantModel',
    'MarketPerception', 'PerceptionSignal', 'PerceptionModel',
    'TradingPlan', 'PlanningSignal', 'PlanningModel',
    'Position', 'PortfolioStats', 'PortfolioSignal', 'PortfolioModel',
    'Prediction', 'PredictiveSignal', 'PredictiveModel',
    'ReasoningRule', 'ReasoningResult', 'ReasoningSignal', 'ReasoningModel',
    'Recommendation', 'RecommendationSignal', 'RecommendationModel',
    'RLState', 'RLAction', 'RLExperience', 'RLSignal', 'ReinforcementLearningModel',
    'RelativeStrengthMetrics', 'RelativeStrengthSignal', 'RelativeStrengthModel',
    'RetracementLevel', 'RetracementPattern', 'RetracementSignal', 'RetracementModel',
    'ReversalPattern', 'ReversalSignal', 'ReversalModel',
    'ReversionMetrics', 'ReversionSignal', 'ReversionModel',
    'RotationMetrics', 'RotationSignal', 'RotationModel',
    'Scenario', 'ScenarioResult', 'ScenarioSignal', 'ScenarioModel',
    'SectorMetrics', 'SectorRotation', 'SectorSignal', 'SectorModel',
    'SentimentMetrics', 'SentimentSignal', 'SentimentModel',
    'SharpeMetrics', 'SharpeSignal', 'SharpeModel',
    'SimulationScenario', 'SimulationSignal', 'SimulationModel',
    'SortinoMetrics', 'SortinoSignal', 'SortinoModel',
    'StatArbPair', 'StatArbTrade', 'StatArbSignal', 'StatisticalArbitrageModel',
    'StressScenario', 'StressResult', 'StressSignal', 'StressModel',
    'SupportResistanceLevel', 'SupportResistanceSignal', 'SupportResistanceModel',
    'TrendIndicator', 'TrendAnalysis', 'TrendSignal', 'TrendModel',
    'Trendline', 'TrendlineSignal', 'TrendlineModel',
    'TrianglePattern', 'TriangleSignal', 'TriangleModel',
    'VaRResult', 'VaRReport', 'VaRModel',
    'VolatilityIndicator', 'VolatilityRegime', 'VolatilitySignal', 'VolatilityModel',
    'VolumeIndicator', 'VolumePattern', 'VolumeSignal', 'VolumeModel',
    'WaveletDecomposition', 'WaveletAnalysis', 'WaveletSignal', 'WaveletModel',
    'WedgePattern', 'WedgeSignal', 'WedgeModel',
    'WyckoffPhase', 'WyckoffSignal', 'WyckoffModel',
    
    # Factory functions
    'create_accumulation_model',
    'create_adaptation_model',
    'create_adaptive_model',
    'create_asset_allocation_model',
    'create_basket_trading_model',
    'create_bayesian_model',
    'create_breadth_model',
    'create_breakout_model',
    'create_calmar_model',
    'create_channel_model',
    'create_chaos_model',
    'create_cognition_model',
    'create_complexity_model',
    'create_concentration_model',
    'create_consolidation_model',
    'create_continuation_model',
    'create_convergence_model',
    'create_correlation_model',
    'create_cvar_model',
    'create_decision_model',
    'create_deep_learning_model',
    'create_distribution_model',
    'create_divergence_model',
    'create_diversification_model',
    'create_drawdown_model',
    'create_elliott_wave_model',
    'create_ensemble_model',
    'create_entropy_model',
    'create_evolution_model',
    'create_evolutionary_model',
    'create_excellence_model',
    'create_execution_model',
    'create_exposure_model',
    'create_feedback_model',
    'create_fibonacci_model',
    'create_flag_model',
    'create_forecast_model',
    'create_fractal_model',
    'create_fundamental_model',
    'create_fuzzy_model',
    'create_genetic_model',
    'create_hurst_model',
    'create_hybrid_model',
    'create_improvement_model',
    'create_industry_model',
    'create_intelligence_model',
    'create_learning_model',
    'create_leverage_model',
    'create_lyapunov_model',
    'create_machine_learning_model',
    'create_macro_model',
    'create_margin_model',
    'create_market_cycle_model',
    'create_mean_reversion_model',
    'create_momentum_model',
    'create_monte_carlo_model',
    'create_neuro_model',
    'create_optimization_model',
    'create_pair_trading_model',
    'create_pennant_model',
    'create_perception_model',
    'create_planning_model',
    'create_portfolio_model',
    'create_predictive_model',
    'create_reasoning_model',
    'create_recommendation_model',
    'create_reinforcement_learning_model',
    'create_relative_strength_model',
    'create_retracement_model',
    'create_reversal_model',
    'create_reversion_model',
    'create_rotation_model',
    'create_scenario_model',
    'create_sector_model',
    'create_sentiment_model',
    'create_sharpe_model',
    'create_simulation_model',
    'create_sortino_model',
    'create_statistical_arbitrage_model',
    'create_stress_model',
    'create_support_resistance_model',
    'create_trend_model',
    'create_trendline_model',
    'create_triangle_model',
    'create_var_model',
    'create_volatility_model',
    'create_volume_model',
    'create_wavelet_model',
    'create_wedge_model',
    'create_wyckoff_model',
    
    # Utility functions
    'get_model',
    'get_all_model_names',
    'get_model_info',
    'MODEL_REGISTRY',
    
    # Version info
    '__version__',
    '__author__',
    '__copyright__',
]

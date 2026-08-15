"""
Swing Bot Configuration Package
================================

This package contains all configuration modules for the Swing Bot trading system.
Each configuration file defines specific parameters for different trading strategies,
risk management, market analysis, and system components.

The configurations are organized by functional area:
- Core trading strategies
- Risk management
- Market analysis
- Execution management
- Performance optimization
- System configuration
"""

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    """Configuration loader for Swing Bot"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """Load a specific configuration file by name."""
        config_path = self.config_dir / f"{config_name}_configs.yaml"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            raise FileNotFoundError(f"Configuration {config_name} not found at {config_path}")
    
    def load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load all configuration files."""
        configs = {}
        for config_file in self.config_dir.glob("*_configs.yaml"):
            config_name = config_file.stem.replace("_configs", "")
            try:
                with open(config_file, 'r') as f:
                    configs[config_name] = yaml.safe_load(f)
            except Exception as e:
                print(f"Error loading {config_file}: {e}")
        return configs
    
    def get_config_names(self) -> list:
        """Get list of all available configuration names."""
        return [f.stem.replace("_configs", "") for f in self.config_dir.glob("*_configs.yaml")]


# Singleton config loader instance
config_loader = ConfigLoader()


# Core strategy configurations
from .absorption_configs import absorption
from .accumulation_configs import accumulation
from .adaptation_configs import adaptation
from .adaptation_engine_configs import adaptation_engine
from .adaptive_configs import adaptive
from .after_hours_configs import after_hours
from .ai_engine_configs import ai_engine
from .algos_configs import algos
from .analytics_engine_configs import analytics_engine
from .arbitrage_configs import arbitrage
from .asset_allocation_configs import asset_allocation
from .auction_process_configs import auction_process
from .basket_trading_configs import basket_trading
from .bayesian_configs import bayesian
from .breadth_configs import breadth
from .breakout_configs import breakout
from .calmar_configs import calmar
from .capital_flows_configs import capital_flows
from .channel_configs import channel
from .chaos_configs import chaos
from .cognition_configs import cognition
from .cognition_engine_configs import cognition_engine
from .commercial_configs import commercial
from .complexity_configs import complexity
from .compliance_engine_configs import compliance_engine
from .concentration_configs import concentration
from .consolidation_configs import consolidation
from .continuation_configs import continuation
from .convergence_configs import convergence
from .correlation_configs import correlation
from .cost_analysis_configs import cost_analysis
from .cot_configs import cot
from .cpi_configs import cpi
from .cumulative_delta_configs import cumulative_delta
from .current_account_configs import current_account
from .cvar_configs import cvar
from .decision_configs import decision
from .decision_engine_configs import decision_engine
from .deep_learning_configs import deep_learning
from .default_config import default
from .delta_configs import delta
from .development_config import development
from .distribution_configs import distribution
from .divergence_configs import divergence
from .diversification_configs import diversification
from .drawdown_configs import drawdown
from .earnings_configs import earnings
from .economic_calendar_configs import economic_calendar
from .elliott_wave_configs import elliott_wave
from .employment_configs import employment
from .ems_configs import ems
from .ensemble_configs import ensemble
from .entropy_configs import entropy
from .evolution_configs import evolution
from .evolution_engine_configs import evolution_engine
from .evolutionary_configs import evolutionary
from .excellence_configs import excellence
from .excellence_engine_configs import excellence_engine
from .execution_configs import execution
from .execution_engine_configs import execution_engine
from .execution_quality_configs import execution_quality
from .exposure_configs import exposure
from .fakeout_configs import fakeout
from .fed_meeting_configs import fed_meeting
from .feedback_configs import feedback
from .feedback_engine_configs import feedback_engine
from .fibonacci_configs import fibonacci
from .fix_configs import fix
from .flag_configs import flag
from .fomo_configs import fomo
from .footprint_configs import footprint
from .forecast_configs import forecast
from .forecast_engine_configs import forecast_engine
from .fractal_configs import fractal
from .fud_configs import fud
from .fundamental_configs import fundamental
from .fuzzy_configs import fuzzy
from .gdp_configs import gdp
from .genetic_configs import genetic
from .globex_configs import globex
from .harmonic_configs import harmonic
from .hedging_configs import hedging
from .hft_configs import hft
from .housing_configs import housing
from .hurst_configs import hurst
from .hybrid_configs import hybrid
from .iceberg_configs import iceberg
from .implementation_shortfall_configs import implementation_shortfall
from .improvement_configs import improvement
from .improvement_engine_configs import improvement_engine
from .industry_configs import industry
from .institutional_configs import institutional
from .intelligence_configs import intelligence
from .intelligence_engine_configs import intelligence_engine
from .layered_manipulation_configs import layered_manipulation
from .learning_configs import learning
from .learning_engine_configs import learning_engine
from .level_configs import level
from .leverage_configs import leverage
from .liquidity_configs import liquidity
from .lyapunov_configs import lyapunov
from .machine_learning_configs import machine_learning
from .macro_configs import macro
from .manufacturing_configs import manufacturing
from .margin_configs import margin
from .market_cycle_configs import market_cycle
from .market_impact_configs import market_impact
from .market_making_configs import market_making
from .market_profile_configs import market_profile
from .mean_reversion_configs import mean_reversion
from .ml_engine_configs import ml_engine
from .momentum_configs import momentum
from .monte_carlo_configs import monte_carlo
from .neuro_configs import neuro
from .news_configs import news
from .nlp_engine_configs import nlp_engine
from .oms_configs import oms
from .optimization_configs import optimization
from .optimization_engine_configs import optimization_engine
from .order_flow_configs import order_flow
from .order_flow_imbalance_configs import order_flow_imbalance
from .overnight_gap_configs import overnight_gap
from .pair_trading_configs import pair_trading
from .participation_rate_configs import participation_rate
from .pennant_configs import pennant
from .perception_configs import perception
from .perception_engine_configs import perception_engine
from .planning_configs import planning
from .planning_engine_configs import planning_engine
from .pms_configs import pms
from .poc_configs import poc
from .portfolio_configs import portfolio
from .post_trade_configs import post_trade
from .power_hour_configs import power_hour
from .ppi_configs import ppi
from .pre_market_configs import pre_market
from .prediction_engine_configs import prediction_engine
from .predictive_configs import predictive
from .production_config import production
from .reasoning_configs import reasoning
from .reasoning_engine_configs import reasoning_engine
from .recommendation_configs import recommendation
from .recommendation_engine_configs import recommendation_engine
from .reinforcement_learning_configs import reinforcement_learning
from .relative_strength_configs import relative_strength
from .reporting_engine_configs import reporting_engine
from .retail_configs import retail
from .retail_sales_configs import retail_sales
from .retracement_configs import retracement
from .reversal_configs import reversal
from .reversion_configs import reversion
from .risk_configs import risk
from .risk_engine_configs import risk_engine
from .rotation_configs import rotation
from .scenario_configs import scenario
from .sector_configs import sector
from .sentiment_configs import sentiment
from .sentiment_engine_configs import sentiment_engine
from .services_configs import services
from .session_analysis_configs import session_analysis
from .session_configs import session
from .sharpe_configs import sharpe
from .simulation_configs import simulation
from .simulation_engine_configs import simulation_engine
from .slippage_control_configs import slippage_control
from .small_spec_configs import small_spec
from .smart_money_configs import smart_money
from .sniper_config import sniper
from .sortino_configs import sortino
from .speculative_configs import speculative
from .spoofing_configs import spoofing
from .statistical_arbitrage_configs import statistical_arbitrage
from .stop_hunting_configs import stop_hunting
from .strategy_configs import strategy
from .stress_configs import stress
from .support_resistance_configs import support_resistance
from .swing_config import swing
from .target_configs import target
from .tca_configs import tca
from .time_price_opportunity_configs import time_price_opportunity
from .trade_balance_configs import trade_balance
from .trend_configs import trend
from .trendline_configs import trendline
from .triangle_configs import triangle
from .twap_configs import twap
from .vah_val_configs import vah_val
from .var_configs import var
from .volatility_configs import volatility
from .volume_analysis_configs import volume_analysis
from .volume_configs import volume
from .volume_imbalance_configs import volume_imbalance
from .volume_node_configs import volume_node
from .volume_profile_configs import volume_profile
from .vsa_configs import vsa
from .vwap_configs import vwap
from .wavelet_configs import wavelet
from .wedge_configs import wedge
from .whale_tracking_configs import whale_tracking
from .wyckoff_configs import wyckoff


# Configuration registry - mapping of config names to their loaded config dictionaries
CONFIG_REGISTRY = {
    # Core strategy
    'absorption': absorption,
    'accumulation': accumulation,
    'adaptation': adaptation,
    'adaptation_engine': adaptation_engine,
    'adaptive': adaptive,
    'after_hours': after_hours,
    'ai_engine': ai_engine,
    'algos': algos,
    'analytics_engine': analytics_engine,
    'arbitrage': arbitrage,
    'asset_allocation': asset_allocation,
    'auction_process': auction_process,
    'basket_trading': basket_trading,
    'bayesian': bayesian,
    'breadth': breadth,
    'breakout': breakout,
    'calmar': calmar,
    'capital_flows': capital_flows,
    'channel': channel,
    'chaos': chaos,
    'cognition': cognition,
    'cognition_engine': cognition_engine,
    'commercial': commercial,
    'complexity': complexity,
    'compliance_engine': compliance_engine,
    'concentration': concentration,
    'consolidation': consolidation,
    'continuation': continuation,
    'convergence': convergence,
    'correlation': correlation,
    'cost_analysis': cost_analysis,
    'cot': cot,
    'cpi': cpi,
    'cumulative_delta': cumulative_delta,
    'current_account': current_account,
    'cvar': cvar,
    'decision': decision,
    'decision_engine': decision_engine,
    'deep_learning': deep_learning,
    'default': default,
    'delta': delta,
    'development': development,
    'distribution': distribution,
    'divergence': divergence,
    'diversification': diversification,
    'drawdown': drawdown,
    'earnings': earnings,
    'economic_calendar': economic_calendar,
    'elliott_wave': elliott_wave,
    'employment': employment,
    'ems': ems,
    'ensemble': ensemble,
    'entropy': entropy,
    'evolution': evolution,
    'evolution_engine': evolution_engine,
    'evolutionary': evolutionary,
    'excellence': excellence,
    'excellence_engine': excellence_engine,
    'execution': execution,
    'execution_engine': execution_engine,
    'execution_quality': execution_quality,
    'exposure': exposure,
    'fakeout': fakeout,
    'fed_meeting': fed_meeting,
    'feedback': feedback,
    'feedback_engine': feedback_engine,
    'fibonacci': fibonacci,
    'fix': fix,
    'flag': flag,
    'fomo': fomo,
    'footprint': footprint,
    'forecast': forecast,
    'forecast_engine': forecast_engine,
    'fractal': fractal,
    'fud': fud,
    'fundamental': fundamental,
    'fuzzy': fuzzy,
    'gdp': gdp,
    'genetic': genetic,
    'globex': globex,
    'harmonic': harmonic,
    'hedging': hedging,
    'hft': hft,
    'housing': housing,
    'hurst': hurst,
    'hybrid': hybrid,
    'iceberg': iceberg,
    'implementation_shortfall': implementation_shortfall,
    'improvement': improvement,
    'improvement_engine': improvement_engine,
    'industry': industry,
    'institutional': institutional,
    'intelligence': intelligence,
    'intelligence_engine': intelligence_engine,
    'layered_manipulation': layered_manipulation,
    'learning': learning,
    'learning_engine': learning_engine,
    'level': level,
    'leverage': leverage,
    'liquidity': liquidity,
    'lyapunov': lyapunov,
    'machine_learning': machine_learning,
    'macro': macro,
    'manufacturing': manufacturing,
    'margin': margin,
    'market_cycle': market_cycle,
    'market_impact': market_impact,
    'market_making': market_making,
    'market_profile': market_profile,
    'mean_reversion': mean_reversion,
    'ml_engine': ml_engine,
    'momentum': momentum,
    'monte_carlo': monte_carlo,
    'neuro': neuro,
    'news': news,
    'nlp_engine': nlp_engine,
    'oms': oms,
    'optimization': optimization,
    'optimization_engine': optimization_engine,
    'order_flow': order_flow,
    'order_flow_imbalance': order_flow_imbalance,
    'overnight_gap': overnight_gap,
    'pair_trading': pair_trading,
    'participation_rate': participation_rate,
    'pennant': pennant,
    'perception': perception,
    'perception_engine': perception_engine,
    'planning': planning,
    'planning_engine': planning_engine,
    'pms': pms,
    'poc': poc,
    'portfolio': portfolio,
    'post_trade': post_trade,
    'power_hour': power_hour,
    'ppi': ppi,
    'pre_market': pre_market,
    'prediction_engine': prediction_engine,
    'predictive': predictive,
    'production': production,
    'reasoning': reasoning,
    'reasoning_engine': reasoning_engine,
    'recommendation': recommendation,
    'recommendation_engine': recommendation_engine,
    'reinforcement_learning': reinforcement_learning,
    'relative_strength': relative_strength,
    'reporting_engine': reporting_engine,
    'retail': retail,
    'retail_sales': retail_sales,
    'retracement': retracement,
    'reversal': reversal,
    'reversion': reversion,
    'risk': risk,
    'risk_engine': risk_engine,
    'rotation': rotation,
    'scenario': scenario,
    'sector': sector,
    'sentiment': sentiment,
    'sentiment_engine': sentiment_engine,
    'services': services,
    'session_analysis': session_analysis,
    'session': session,
    'sharpe': sharpe,
    'simulation': simulation,
    'simulation_engine': simulation_engine,
    'slippage_control': slippage_control,
    'small_spec': small_spec,
    'smart_money': smart_money,
    'sniper': sniper,
    'sortino': sortino,
    'speculative': speculative,
    'spoofing': spoofing,
    'statistical_arbitrage': statistical_arbitrage,
    'stop_hunting': stop_hunting,
    'strategy': strategy,
    'stress': stress,
    'support_resistance': support_resistance,
    'swing': swing,
    'target': target,
    'tca': tca,
    'time_price_opportunity': time_price_opportunity,
    'trade_balance': trade_balance,
    'trend': trend,
    'trendline': trendline,
    'triangle': triangle,
    'twap': twap,
    'vah_val': vah_val,
    'var': var,
    'volatility': volatility,
    'volume_analysis': volume_analysis,
    'volume': volume,
    'volume_imbalance': volume_imbalance,
    'volume_node': volume_node,
    'volume_profile': volume_profile,
    'vsa': vsa,
    'vwap': vwap,
    'wavelet': wavelet,
    'wedge': wedge,
    'whale_tracking': whale_tracking,
    'wyckoff': wyckoff,
}


def get_config(config_name: str) -> Dict[str, Any]:
    """
    Get a specific configuration by name.
    
    Args:
        config_name: Name of the configuration to retrieve
        
    Returns:
        Dictionary containing the configuration
    """
    if config_name in CONFIG_REGISTRY:
        return CONFIG_REGISTRY[config_name]
    else:
        # Try to load from file
        try:
            return config_loader.load_config(config_name)
        except FileNotFoundError:
            raise KeyError(f"Configuration '{config_name}' not found")


def get_all_configs() -> Dict[str, Dict[str, Any]]:
    """
    Get all loaded configurations.
    
    Returns:
        Dictionary containing all configurations
    """
    return CONFIG_REGISTRY.copy()


def get_config_names() -> list:
    """
    Get list of all available configuration names.
    
    Returns:
        List of configuration names
    """
    return list(CONFIG_REGISTRY.keys())


def reload_config(config_name: str) -> Dict[str, Any]:
    """
    Reload a specific configuration from file.
    
    Args:
        config_name: Name of the configuration to reload
        
    Returns:
        Dictionary containing the reloaded configuration
    """
    config = config_loader.load_config(config_name)
    CONFIG_REGISTRY[config_name] = config
    return config


def reload_all_configs() -> Dict[str, Dict[str, Any]]:
    """
    Reload all configurations from files.
    
    Returns:
        Dictionary containing all reloaded configurations
    """
    all_configs = config_loader.load_all_configs()
    CONFIG_REGISTRY.update(all_configs)
    return CONFIG_REGISTRY


# Version information
VERSION = __version__
AUTHOR = __author__
COPYRIGHT = __copyright__


__all__ = [
    # Core functions
    'ConfigLoader',
    'config_loader',
    'get_config',
    'get_all_configs',
    'get_config_names',
    'reload_config',
    'reload_all_configs',
    
    # Version info
    'VERSION',
    'AUTHOR',
    'COPYRIGHT',
    
    # Configuration registry
    'CONFIG_REGISTRY',
    
    # All config names
    'absorption',
    'accumulation',
    'adaptation',
    'adaptation_engine',
    'adaptive',
    'after_hours',
    'ai_engine',
    'algos',
    'analytics_engine',
    'arbitrage',
    'asset_allocation',
    'auction_process',
    'basket_trading',
    'bayesian',
    'breadth',
    'breakout',
    'calmar',
    'capital_flows',
    'channel',
    'chaos',
    'cognition',
    'cognition_engine',
    'commercial',
    'complexity',
    'compliance_engine',
    'concentration',
    'consolidation',
    'continuation',
    'convergence',
    'correlation',
    'cost_analysis',
    'cot',
    'cpi',
    'cumulative_delta',
    'current_account',
    'cvar',
    'decision',
    'decision_engine',
    'deep_learning',
    'default',
    'delta',
    'development',
    'distribution',
    'divergence',
    'diversification',
    'drawdown',
    'earnings',
    'economic_calendar',
    'elliott_wave',
    'employment',
    'ems',
    'ensemble',
    'entropy',
    'evolution',
    'evolution_engine',
    'evolutionary',
    'excellence',
    'excellence_engine',
    'execution',
    'execution_engine',
    'execution_quality',
    'exposure',
    'fakeout',
    'fed_meeting',
    'feedback',
    'feedback_engine',
    'fibonacci',
    'fix',
    'flag',
    'fomo',
    'footprint',
    'forecast',
    'forecast_engine',
    'fractal',
    'fud',
    'fundamental',
    'fuzzy',
    'gdp',
    'genetic',
    'globex',
    'harmonic',
    'hedging',
    'hft',
    'housing',
    'hurst',
    'hybrid',
    'iceberg',
    'implementation_shortfall',
    'improvement',
    'improvement_engine',
    'industry',
    'institutional',
    'intelligence',
    'intelligence_engine',
    'layered_manipulation',
    'learning',
    'learning_engine',
    'level',
    'leverage',
    'liquidity',
    'lyapunov',
    'machine_learning',
    'macro',
    'manufacturing',
    'margin',
    'market_cycle',
    'market_impact',
    'market_making',
    'market_profile',
    'mean_reversion',
    'ml_engine',
    'momentum',
    'monte_carlo',
    'neuro',
    'news',
    'nlp_engine',
    'oms',
    'optimization',
    'optimization_engine',
    'order_flow',
    'order_flow_imbalance',
    'overnight_gap',
    'pair_trading',
    'participation_rate',
    'pennant',
    'perception',
    'perception_engine',
    'planning',
    'planning_engine',
    'pms',
    'poc',
    'portfolio',
    'post_trade',
    'power_hour',
    'ppi',
    'pre_market',
    'prediction_engine',
    'predictive',
    'production',
    'reasoning',
    'reasoning_engine',
    'recommendation',
    'recommendation_engine',
    'reinforcement_learning',
    'relative_strength',
    'reporting_engine',
    'retail',
    'retail_sales',
    'retracement',
    'reversal',
    'reversion',
    'risk',
    'risk_engine',
    'rotation',
    'scenario',
    'sector',
    'sentiment',
    'sentiment_engine',
    'services',
    'session_analysis',
    'session',
    'sharpe',
    'simulation',
    'simulation_engine',
    'slippage_control',
    'small_spec',
    'smart_money',
    'sniper',
    'sortino',
    'speculative',
    'spoofing',
    'statistical_arbitrage',
    'stop_hunting',
    'strategy',
    'stress',
    'support_resistance',
    'swing',
    'target',
    'tca',
    'time_price_opportunity',
    'trade_balance',
    'trend',
    'trendline',
    'triangle',
    'twap',
    'vah_val',
    'var',
    'volatility',
    'volume_analysis',
    'volume',
    'volume_imbalance',
    'volume_node',
    'volume_profile',
    'vsa',
    'vwap',
    'wavelet',
    'wedge',
    'whale_tracking',
    'wyckoff',
]

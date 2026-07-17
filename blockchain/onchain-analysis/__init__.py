# blockchain/onchain-analysis/__init__.py
# NEXUS AI TRADING SYSTEM - On-Chain Analysis Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
On-Chain Analysis Module for NEXUS AI TRADING SYSTEM.

This module provides comprehensive on-chain data analysis capabilities including:
- Whale tracking and monitoring
- Smart money analysis
- Exchange flow analysis
- Token analytics
- Volume analysis
- Gas analysis
- Mempool analysis
- DeFi protocol analysis
- NFT analysis
- On-chain metrics and signals
- Anomaly detection
- Risk assessment
- Sentiment analysis

All components are designed to work together to provide a complete picture
of on-chain activity across multiple blockchains.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from blockchain.onchain_analysis.base_analyzer import BaseOnChainAnalyzer
from blockchain.onchain_analysis.defi_analyzer import DeFiAnalyzer, create_defi_analyzer
from blockchain.onchain_analysis.exchange_flow import ExchangeFlowAnalyzer, create_exchange_flow_analyzer
from blockchain.onchain_analysis.gas_analyzer import GasAnalyzer, create_gas_analyzer
from blockchain.onchain_analysis.holder_analyzer import HolderAnalyzer, create_holder_analyzer
from blockchain.onchain_analysis.mempool_analyzer import MempoolAnalyzer, create_mempool_analyzer
from blockchain.onchain_analysis.nft_analyzer import NFTAnalyzer, create_nft_analyzer
from blockchain.onchain_analysis.onchain_alerts import (
    AlertCategory,
    AlertChannel,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    OnChainAlert,
    OnChainAlertEngine,
    create_onchain_alert_engine,
)
from blockchain.onchain_analysis.onchain_analyzer import (
    AnalysisType,
    MarketSentiment,
    OnChainAnalysisConfig,
    OnChainAnalysisResult,
    OnChainAnalyzer,
    OnChainRiskLevel,
    OnChainSnapshot,
    create_onchain_analyzer,
)
from blockchain.onchain_analysis.onchain_metrics import (
    MetricCategory,
    MetricDefinition,
    MetricFrequency,
    MetricStatus,
    MetricValue,
    OnChainMetrics,
    create_onchain_metrics,
)
from blockchain.onchain_analysis.onchain_signals import (
    OnChainSignal,
    OnChainSignalGenerator,
    SignalAggregation,
    SignalCategory,
    SignalDefinition,
    SignalStatus,
    SignalStrength,
    SignalType,
    create_onchain_signal_generator,
)
from blockchain.onchain_analysis.smart_money import (
    SmartMoneyAction,
    SmartMoneyAnalyzer,
    SmartMoneyCluster,
    SmartMoneyConfidence,
    SmartMoneyEntity,
    SmartMoneySignal,
    SmartMoneyType,
    create_smart_money_analyzer,
)
from blockchain.onchain_analysis.token_analyzer import (
    TokenAnalyzer,
    TokenHolder,
    TokenInfo,
    TokenRiskAnalysis,
    TokenRiskLevel,
    TokenStandard,
    TokenStatus,
    TokenSupply,
    TokenTransaction,
    TokenTradingInfo,
    TokenType,
    create_token_analyzer,
)
from blockchain.onchain_analysis.volume_analyzer import (
    VolumeAnalysis,
    VolumeAnalyzer,
    VolumeAnomaly,
    VolumeBreakdown,
    VolumeConfidence,
    VolumeDataPoint,
    VolumePattern,
    VolumeType,
    create_volume_analyzer,
)
from blockchain.onchain_analysis.whale_tracker import (
    Whale,
    WhaleAction,
    WhaleAlert,
    WhaleCluster,
    WhaleConfidence,
    WhaleTracker,
    WhaleTransaction,
    WhaleType,
    create_whale_tracker,
)

# Version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module logger
logger = logging.getLogger("nexus.onchain")

# Export all public components
__all__ = [
    # Base
    "BaseOnChainAnalyzer",
    
    # Core Analyzer
    "OnChainAnalyzer",
    "OnChainAnalysisConfig",
    "OnChainAnalysisResult",
    "OnChainSnapshot",
    "AnalysisType",
    "MarketSentiment",
    "OnChainRiskLevel",
    "create_onchain_analyzer",
    
    # Metrics
    "OnChainMetrics",
    "MetricCategory",
    "MetricDefinition",
    "MetricFrequency",
    "MetricStatus",
    "MetricValue",
    "create_onchain_metrics",
    
    # Signals
    "OnChainSignalGenerator",
    "OnChainSignal",
    "SignalAggregation",
    "SignalDefinition",
    "SignalCategory",
    "SignalStatus",
    "SignalStrength",
    "SignalType",
    "create_onchain_signal_generator",
    
    # Alerts
    "OnChainAlertEngine",
    "OnChainAlert",
    "AlertRule",
    "AlertCategory",
    "AlertChannel",
    "AlertSeverity",
    "AlertStatus",
    "create_onchain_alert_engine",
    
    # Whale Tracking
    "WhaleTracker",
    "Whale",
    "WhaleAction",
    "WhaleAlert",
    "WhaleCluster",
    "WhaleConfidence",
    "WhaleTransaction",
    "WhaleType",
    "create_whale_tracker",
    
    # Smart Money
    "SmartMoneyAnalyzer",
    "SmartMoneyAction",
    "SmartMoneyCluster",
    "SmartMoneyConfidence",
    "SmartMoneyEntity",
    "SmartMoneySignal",
    "SmartMoneyType",
    "create_smart_money_analyzer",
    
    # Token Analysis
    "TokenAnalyzer",
    "TokenHolder",
    "TokenInfo",
    "TokenRiskAnalysis",
    "TokenRiskLevel",
    "TokenStandard",
    "TokenStatus",
    "TokenSupply",
    "TokenTransaction",
    "TokenTradingInfo",
    "TokenType",
    "create_token_analyzer",
    
    # Volume Analysis
    "VolumeAnalyzer",
    "VolumeAnalysis",
    "VolumeAnomaly",
    "VolumeBreakdown",
    "VolumeConfidence",
    "VolumeDataPoint",
    "VolumePattern",
    "VolumeType",
    "create_volume_analyzer",
    
    # Exchange Flow
    "ExchangeFlowAnalyzer",
    "create_exchange_flow_analyzer",
    
    # Gas Analysis
    "GasAnalyzer",
    "create_gas_analyzer",
    
    # Holder Analysis
    "HolderAnalyzer",
    "create_holder_analyzer",
    
    # Mempool Analysis
    "MempoolAnalyzer",
    "create_mempool_analyzer",
    
    # DeFi Analysis
    "DeFiAnalyzer",
    "create_defi_analyzer",
    
    # NFT Analysis
    "NFTAnalyzer",
    "create_nft_analyzer",
]

# ============================================================================
# Module Information
# ============================================================================

MODULE_INFO = {
    "name": "On-Chain Analysis",
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "description": "Comprehensive on-chain data analysis for NEXUS AI Trading System",
    "components": [
        "Core Analyzer",
        "Metrics Engine",
        "Signal Generator",
        "Alert Engine",
        "Whale Tracker",
        "Smart Money Analyzer",
        "Token Analyzer",
        "Volume Analyzer",
        "Exchange Flow Analyzer",
        "Gas Analyzer",
        "Holder Analyzer",
        "Mempool Analyzer",
        "DeFi Analyzer",
        "NFT Analyzer",
    ],
    "chains_supported": ["Ethereum", "BNB Chain", "Polygon", "Arbitrum", "Optimism", "Solana"],
    "features": [
        "Real-time whale tracking",
        "Smart money detection",
        "Exchange flow monitoring",
        "Token supply analysis",
        "Holder distribution analysis",
        "Volume pattern detection",
        "Gas price forecasting",
        "Mempool analysis",
        "DeFi protocol analytics",
        "NFT market analysis",
        "Risk assessment",
        "Sentiment analysis",
        "Anomaly detection",
        "Trading signal generation",
    ],
}


def get_module_info() -> Dict[str, Any]:
    """Get module information."""
    return MODULE_INFO


def get_version() -> str:
    """Get module version."""
    return __version__


# ============================================================================
# Module Initialization
# ============================================================================

def initialize_module(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Initialize the on-chain analysis module.
    
    Args:
        config: Configuration dictionary for the module
        
    Returns:
        Dictionary containing initialized components
    """
    logger.info("Initializing On-Chain Analysis Module...")
    
    config = config or {}
    
    # Components that will be initialized
    components = {}
    
    try:
        # Core components would be initialized here
        # with proper Web3 client and dependencies
        
        logger.info("On-Chain Analysis Module initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize On-Chain Analysis Module: {e}")
        raise
    
    return components


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Print module info
    print(f"On-Chain Analysis Module v{__version__}")
    print(f"Author: {__author__}")
    print(f"\nSupported Components:")
    for component in MODULE_INFO["components"]:
        print(f"  - {component}")
    print(f"\nSupported Chains:")
    for chain in MODULE_INFO["chains_supported"]:
        print(f"  - {chain}")

"""
NEXUS AI TRADING SYSTEM - Walk-Forward Analysis
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Walk-Forward Analysis system with:
- Walk-forward optimization
- Rolling window analysis
- Expanding window analysis
- Out-of-sample testing
- Parameter stability analysis
- Performance visualization
- Export capabilities
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import WalkForwardError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class WindowType(str, Enum):
    """Window types"""
    ROLLING = "rolling"
    EXPANDING = "expanding"
    FIXED = "fixed"


@dataclass
class WalkForwardConfig:
    """Walk-forward configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    train_window: int = 252  # Days
    test_window: int = 63    # Days
    step_size: int = 21      # Days
    window_type: WindowType = WindowType.ROLLING
    min_train_size: int = 100
    max_train_size: int = 1000
    optimize_every: int = 1
    parallel_workers: int = 4
    save_intermediate: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardResult:
    """Walk-forward result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    window_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_params: Dict[str, Any] = field(default_factory=dict)
    test_metrics: Dict[str, Any] = field(default_factory=dict)
    train_metrics: Dict[str, Any] = field(default_factory=dict)
    test_performance: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardSummary:
    """Walk-forward summary"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    total_windows: int
    total_train_days: int
    total_test_days: int
    avg_train_metrics: Dict[str, Any] = field(default_factory=dict)
    avg_test_metrics: Dict[str, Any] = field(default_factory=dict)
    parameter_stability: Dict[str, Any] = field(default_factory=dict)
    performance_consistency: Dict[str, Any] = field(default_factory=dict)
    best_window: Optional[int] = None
    worst_window: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ========================================
# WALK-FORWARD ANALYZER
# ========================================

class WalkForwardAnalyzer:
    """
    Complete walk-forward analysis for strategy validation.
    
    Features:
    - Walk-forward optimization
    - Rolling window analysis
    - Expanding window analysis
    - Out-of-sample testing
    - Parameter stability analysis
    - Performance visualization
    - Export capabilities
    - Health monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.redis = get_redis()
        
        # State
        self._results: Dict[str, WalkForwardResult] = {}
        self._summaries: Dict[str, WalkForwardSummary] = {}
        self._running_analyses: Dict[str, asyncio.Task] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_analyses": 0,
            "completed_analyses": 0,
            "failed_analyses": 0,
            "total_windows": 0,
            "avg_analysis_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.WalkForwardAnalyzer")
        self.logger.info("WalkForwardAnalyzer initialized")
    
    # ========================================
    # MAIN ANALYSIS
    # ========================================
    
    async def analyze(
        self,
        config: WalkForwardConfig,
        data: pd.DataFrame,
        objective_function: Callable,
        parameter_space: Dict[str, List[Any]]
    ) -> WalkForwardSummary:
        """
        Run walk-forward analysis.
        
        Args:
            config: Walk-forward configuration
            data: Historical data
            objective_function: Function to optimize
            parameter_space: Parameter search space
            
        Returns:
            WalkForwardSummary: Analysis summary
        """
        start_time = time.time()
        
        try:
            # Validate data
            if data.empty:
                raise WalkForwardError("Empty data provided")
            
            # Generate windows
            windows = self._generate_windows(config, data)
            
            if not windows:
                raise WalkForwardError("No windows generated")
            
            # Initialize summary
            summary = WalkForwardSummary(
                config_id=config.id,
                total_windows=len(windows)
            )
            
            # Process each window
            for i, window in enumerate(windows):
                self.logger.info(f"Processing window {i+1}/{len(windows)}")
                
                # Split data
                train_data = data.iloc[window['train_start']:window['train_end']]
                test_data = data.iloc[window['test_start']:window['test_end']]
                
                # Optimize on training data
                best_params = await self._optimize_window(
                    objective_function,
                    parameter_space,
                    train_data
                )
                
                # Test on out-of-sample data
                test_performance = await self._test_window(
                    objective_function,
                    best_params,
                    test_data
                )
                
                # Train performance
                train_performance = await self._test_window(
                    objective_function,
                    best_params,
                    train_data
                )
                
                # Store result
                result = WalkForwardResult(
                    config_id=config.id,
                    window_index=i,
                    train_start=window['train_start'],
                    train_end=window['train_end'],
                    test_start=window['test_start'],
                    test_end=window['test_end'],
                    train_params=best_params,
                    train_metrics=train_performance,
                    test_metrics=test_performance,
                    test_performance=test_performance
                )
                
                self._results[result.id] = result
                
                # Update summary
                self._update_summary(summary, result)
                
                self._metrics["total_windows"] += 1
            
            # Finalize summary
            summary = await self._finalize_summary(summary)
            self._summaries[config.id] = summary
            
            # Update metrics
            elapsed = time.time() - start_time
            self._metrics["total_analyses"] += 1
            self._metrics["completed_analyses"] += 1
            self._metrics["avg_analysis_time"] = (
                self._metrics["avg_analysis_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(
                f"Walk-forward analysis completed: {config.name} "
                f"({len(windows)} windows) in {elapsed:.2f}s"
            )
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Walk-forward analysis failed: {e}")
            self._metrics["failed_analyses"] += 1
            raise WalkForwardError(f"Analysis failed: {e}")
    
    # ========================================
    # WINDOW GENERATION
    # ========================================
    
    def _generate_windows(
        self,
        config: WalkForwardConfig,
        data: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Generate train-test windows"""
        windows = []
        data_len = len(data)
        
        if config.window_type == WindowType.ROLLING:
            # Rolling windows
            train_size = config.train_window
            test_size = config.test_window
            step = config.step_size
            
            start = 0
            while start + train_size + test_size <= data_len:
                train_start = start
                train_end = start + train_size
                test_start = train_end
                test_end = min(test_start + test_size, data_len)
                
                windows.append({
                    'train_start': train_start,
                    'train_end': train_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'start_date': data.index[train_start],
                    'end_date': data.index[test_end - 1]
                })
                
                start += step
                
                # Check if we should stop
                if config.max_train_size and train_size >= config.max_train_size:
                    break
                
                # Increase train size for expanding windows
                if config.window_type == WindowType.EXPANDING:
                    train_size += step
        
        elif config.window_type == WindowType.EXPANDING:
            # Expanding windows
            train_size = config.min_train_size
            test_size = config.test_window
            step = config.step_size
            
            while train_size + test_size <= data_len:
                train_start = 0
                train_end = train_size
                test_start = train_end
                test_end = min(test_start + test_size, data_len)
                
                windows.append({
                    'train_start': train_start,
                    'train_end': train_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'start_date': data.index[train_start],
                    'end_date': data.index[test_end - 1]
                })
                
                train_size += step
                
                if config.max_train_size and train_size >= config.max_train_size:
                    break
        
        else:
            # Fixed windows
            train_size = config.train_window
            test_size = config.test_window
            step = config.step_size
            
            for i in range(0, data_len - train_size - test_size + 1, step):
                windows.append({
                    'train_start': i,
                    'train_end': i + train_size,
                    'test_start': i + train_size,
                    'test_end': min(i + train_size + test_size, data_len),
                    'start_date': data.index[i],
                    'end_date': data.index[min(i + train_size + test_size - 1, data_len - 1)]
                })
        
        return windows
    
    # ========================================
    # OPTIMIZATION
    # ========================================
    
    async def _optimize_window(
        self,
        objective_function: Callable,
        parameter_space: Dict[str, List[Any]],
        train_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Optimize parameters for a window"""
        best_params = None
        best_score = -float('inf')
        
        # Grid search over parameter space
        import itertools
        
        keys = list(parameter_space.keys())
        values = list(parameter_space.values())
        
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            
            try:
                # Calculate objective on training data
                score = await self._evaluate_parameters(
                    objective_function,
                    params,
                    train_data
                )
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    
            except Exception as e:
                self.logger.warning(f"Parameter combination failed: {e}")
                continue
        
        return best_params or {}
    
    async def _evaluate_parameters(
        self,
        objective_function: Callable,
        params: Dict[str, Any],
        data: pd.DataFrame
    ) -> float:
        """Evaluate parameters on data"""
        try:
            result = objective_function(params, data)
            return float(result)
        except Exception as e:
            self.logger.warning(f"Parameter evaluation failed: {e}")
            return -float('inf')
    
    async def _test_window(
        self,
        objective_function: Callable,
        params: Dict[str, Any],
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Test parameters on out-of-sample data"""
        try:
            result = objective_function(params, data)
            
            # Convert to dict if not already
            if isinstance(result, (int, float)):
                return {'score': result}
            elif isinstance(result, dict):
                return result
            else:
                return {'result': str(result)}
                
        except Exception as e:
            self.logger.warning(f"Window testing failed: {e}")
            return {'error': str(e)}
    
    # ========================================
    # SUMMARY CALCULATION
    # ========================================
    
    def _update_summary(
        self,
        summary: WalkForwardSummary,
        result: WalkForwardResult
    ) -> None:
        """Update summary with result"""
        # Accumulate metrics
        for key, value in result.train_metrics.items():
            if isinstance(value, (int, float)):
                if key not in summary.avg_train_metrics:
                    summary.avg_train_metrics[key] = []
                summary.avg_train_metrics[key].append(value)
        
        for key, value in result.test_metrics.items():
            if isinstance(value, (int, float)):
                if key not in summary.avg_test_metrics:
                    summary.avg_test_metrics[key] = []
                summary.avg_test_metrics[key].append(value)
        
        # Track parameter stability
        for key, value in result.train_params.items():
            if isinstance(value, (int, float)):
                if key not in summary.parameter_stability:
                    summary.parameter_stability[key] = []
                summary.parameter_stability[key].append(value)
    
    async def _finalize_summary(
        self,
        summary: WalkForwardSummary
    ) -> WalkForwardSummary:
        """Finalize summary calculations"""
        # Calculate averages
        for key, values in summary.avg_train_metrics.items():
            if values:
                summary.avg_train_metrics[key] = np.mean(values)
            else:
                summary.avg_train_metrics[key] = 0.0
        
        for key, values in summary.avg_test_metrics.items():
            if values:
                summary.avg_test_metrics[key] = np.mean(values)
            else:
                summary.avg_test_metrics[key] = 0.0
        
        # Calculate parameter stability
        for key, values in summary.parameter_stability.items():
            if values:
                summary.parameter_stability[key] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': min(values),
                    'max': max(values)
                }
            else:
                summary.parameter_stability[key] = {}
        
        # Calculate performance consistency
        if summary.avg_train_metrics and summary.avg_test_metrics:
            summary.performance_consistency = {
                'train_test_ratio': {
                    key: summary.avg_test_metrics.get(key, 0) / (summary.avg_train_metrics.get(key, 0) + 0.001)
                    for key in summary.avg_train_metrics.keys()
                    if key in summary.avg_test_metrics
                }
            }
        
        # Find best and worst windows
        if summary.avg_test_metrics:
            scores = []
            for result_id, result in self._results.items():
                if result.config_id == summary.config_id:
                    score = result.test_metrics.get('score', 0)
                    scores.append((result.window_index, score))
            
            if scores:
                best = max(scores, key=lambda x: x[1])
                worst = min(scores, key=lambda x: x[1])
                summary.best_window = best[0]
                summary.worst_window = worst[0]
        
        return summary
    
    # ========================================
    # VISUALIZATION
    # ========================================
    
    async def create_charts(
        self,
        config_id: str
    ) -> Dict[str, str]:
        """
        Create visual charts for walk-forward analysis.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Dict[str, str]: Chart data URLs
        """
        summary = self._summaries.get(config_id)
        if not summary:
            raise WalkForwardError(f"Summary {config_id} not found")
        
        charts = {}
        
        # Collect results
        results = []
        for result in self._results.values():
            if result.config_id == config_id:
                results.append(result)
        
        if not results:
            return charts
        
        # Sort by window index
        results.sort(key=lambda x: x.window_index)
        
        # Performance chart
        fig1 = go.Figure()
        
        train_scores = [r.train_metrics.get('score', 0) for r in results]
        test_scores = [r.test_metrics.get('score', 0) for r in results]
        
        fig1.add_trace(go.Scatter(
            y=train_scores,
            mode='lines+markers',
            name='Train Score',
            line=dict(color='#3b82f6', width=2)
        ))
        
        fig1.add_trace(go.Scatter(
            y=test_scores,
            mode='lines+markers',
            name='Test Score',
            line=dict(color='#22c55e', width=2)
        ))
        
        fig1.update_layout(
            title='Walk-Forward Performance',
            xaxis_title='Window',
            yaxis_title='Score',
            template='plotly_white',
            height=400
        )
        
        charts['performance'] = fig1.to_html(full_html=False)
        
        # Parameter stability chart
        if summary.parameter_stability:
            fig2 = go.Figure()
            
            for param_name, values in summary.parameter_stability.items():
                fig2.add_trace(go.Scatter(
                    y=values.get('values', []),
                    mode='lines+markers',
                    name=param_name
                ))
            
            fig2.update_layout(
                title='Parameter Stability',
                xaxis_title='Window',
                yaxis_title='Parameter Value',
                template='plotly_white',
                height=400
            )
            
            charts['parameters'] = fig2.to_html(full_html=False)
        
        # Train-Test comparison chart
        fig3 = go.Figure()
        
        for key in summary.avg_train_metrics.keys():
            if key in summary.avg_test_metrics:
                train_values = [r.train_metrics.get(key, 0) for r in results]
                test_values = [r.test_metrics.get(key, 0) for r in results]
                
                fig3.add_trace(go.Scatter(
                    y=train_values,
                    mode='lines',
                    name=f'Train {key}',
                    line=dict(width=1)
                ))
                
                fig3.add_trace(go.Scatter(
                    y=test_values,
                    mode='lines',
                    name=f'Test {key}',
                    line=dict(width=1, dash='dash')
                ))
        
        fig3.update_layout(
            title='Train vs Test Comparison',
            xaxis_title='Window',
            yaxis_title='Metric Value',
            template='plotly_white',
            height=400
        )
        
        charts['comparison'] = fig3.to_html(full_html=False)
        
        return charts
    
    # ========================================
    # EXPORT
    # ========================================
    
    async def export_results(
        self,
        config_id: str,
        format: str = 'json'
    ) -> str:
        """
        Export walk-forward results.
        
        Args:
            config_id: Configuration ID
            format: Export format ('json', 'csv')
            
        Returns:
            str: Exported data
        """
        summary = self._summaries.get(config_id)
        if not summary:
            raise WalkForwardError(f"Summary {config_id} not found")
        
        if format == 'json':
            return self._export_json(config_id)
        elif format == 'csv':
            return await self._export_csv(config_id)
        else:
            raise WalkForwardError(f"Unsupported format: {format}")
    
    def _export_json(self, config_id: str) -> str:
        """Export as JSON"""
        results = []
        for result in self._results.values():
            if result.config_id == config_id:
                results.append(result.__dict__)
        
        summary = self._summaries.get(config_id)
        
        return json.dumps({
            'summary': summary.__dict__ if summary else {},
            'results': results
        }, default=str, indent=2)
    
    async def _export_csv(self, config_id: str) -> str:
        """Export as CSV"""
        results = []
        for result in self._results.values():
            if result.config_id == config_id:
                results.append({
                    'window': result.window_index,
                    'train_start': result.train_start,
                    'train_end': result.train_end,
                    'test_start': result.test_start,
                    'test_end': result.test_end,
                    'train_score': result.train_metrics.get('score', 0),
                    'test_score': result.test_metrics.get('score', 0)
                })
        
        if results:
            df = pd.DataFrame(results)
            return df.to_csv(index=False)
        
        return ""
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_summary(self, config_id: str) -> Optional[WalkForwardSummary]:
        """Get analysis summary"""
        return self._summaries.get(config_id)
    
    async def get_results(
        self,
        config_id: str
    ) -> List[WalkForwardResult]:
        """Get all results for a configuration"""
        results = []
        for result in self._results.values():
            if result.config_id == config_id:
                results.append(result)
        return results
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get analyzer metrics"""
        return {
            **self._metrics,
            "total_results": len(self._results),
            "total_summaries": len(self._summaries)
        }
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the analyzer"""
        self._running = True
        self.logger.info("WalkForwardAnalyzer started")
    
    async def stop(self) -> None:
        """Stop the analyzer"""
        self._running = False
        
        # Cancel running analyses
        for analysis_id in list(self._running_analyses.keys()):
            task = self._running_analyses[analysis_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._running_analyses.clear()
        self.logger.info("WalkForwardAnalyzer stopped")
    
    async def health_check(self) -> bool:
        """Check analyzer health"""
        try:
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


# ========================================
# DEPENDENCY INJECTION
# ========================================

_walk_forward: Optional[WalkForwardAnalyzer] = None


def get_walk_forward() -> WalkForwardAnalyzer:
    """Get singleton instance of WalkForwardAnalyzer"""
    global _walk_forward
    if _walk_forward is None:
        _walk_forward = WalkForwardAnalyzer()
    return _walk_forward


def reset_walk_forward() -> None:
    """Reset the walk-forward analyzer (for testing)"""
    global _walk_forward
    if _walk_forward:
        asyncio.create_task(_walk_forward.stop())
    _walk_forward = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'WalkForwardAnalyzer',
    'WalkForwardConfig',
    'WalkForwardResult',
    'WalkForwardSummary',
    'WindowType',
    'get_walk_forward',
    'reset_walk_forward'
]

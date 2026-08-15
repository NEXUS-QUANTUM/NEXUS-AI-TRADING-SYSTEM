"""
Swing Bot Report Generator
============================

This module provides report generation capabilities for the Swing Bot trading system.
"""

import json
import csv
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template
import base64
from io import BytesIO

from trading.bots.swing_bot.core import Position, Trade, Portfolio
from trading.bots.swing_bot.utils.formatters import Formatters
from trading.bots.swing_bot.utils.date_utils import DateUtils


class ReportGenerator:
    """
    Generate reports for trading data and performance metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the report generator.
        
        Args:
            config: Report configuration
        """
        self.config = config or {}
        self.output_dir = Path(self.config.get('output_dir', 'reports'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.formats = self.config.get('formats', ['json', 'html', 'csv'])
    
    def generate_performance_report(
        self,
        trades: List[Trade],
        positions: List[Position],
        portfolio: Portfolio,
        metrics: Dict[str, Any],
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a performance report.
        
        Args:
            trades: List of trades
            positions: List of positions
            portfolio: Portfolio data
            metrics: Performance metrics
            output_file: Output file name
        
        Returns:
            Report data
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'period': self._get_period(positions),
            'summary': self._generate_summary(trades, positions, portfolio, metrics),
            'trades': self._format_trades(trades),
            'positions': self._format_positions(positions),
            'portfolio': self._format_portfolio(portfolio),
            'metrics': metrics,
            'charts': self._generate_charts(trades, positions, portfolio)
        }
        
        if output_file:
            self._save_report(report, output_file)
        
        return report
    
    def generate_risk_report(
        self,
        positions: List[Position],
        risk_metrics: Dict[str, Any],
        limits: Dict[str, Any],
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a risk report.
        
        Args:
            positions: List of positions
            risk_metrics: Risk metrics
            limits: Risk limits
            output_file: Output file name
        
        Returns:
            Report data
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': self._generate_risk_summary(positions, risk_metrics, limits),
            'positions': self._format_positions(positions),
            'risk_metrics': risk_metrics,
            'limits': limits,
            'limit_breaches': self._check_limit_breaches(risk_metrics, limits),
            'charts': self._generate_risk_charts(risk_metrics)
        }
        
        if output_file:
            self._save_report(report, output_file)
        
        return report
    
    def generate_daily_report(
        self,
        trades: List[Trade],
        positions: List[Position],
        portfolio: Portfolio,
        metrics: Dict[str, Any],
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a daily report.
        
        Args:
            trades: List of trades
            positions: List of positions
            portfolio: Portfolio data
            metrics: Performance metrics
            output_file: Output file name
        
        Returns:
            Report data
        """
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Filter today's trades
        today_trades = [t for t in trades if t.executed_at and t.executed_at >= today_start]
        
        report = {
            'timestamp': today.isoformat(),
            'date': today.strftime('%Y-%m-%d'),
            'summary': {
                'total_trades': len(today_trades),
                'total_volume': sum(t.quantity * t.price for t in today_trades),
                'pnl': portfolio.calculate_total_pnl(),
                'open_positions': len(positions),
                'cash': portfolio.cash,
                'total_value': portfolio.calculate_total_value()
            },
            'trades': self._format_trades(today_trades),
            'positions': self._format_positions(positions),
            'metrics': metrics
        }
        
        if output_file:
            self._save_report(report, output_file)
        
        return report
    
    def generate_trade_report(
        self,
        trades: List[Trade],
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a trade report.
        
        Args:
            trades: List of trades
            output_file: Output file name
        
        Returns:
            Report data
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_trades': len(trades),
            'trades': self._format_trades(trades),
            'summary': {
                'total_buy_volume': sum(t.quantity * t.price for t in trades if t.side.value == 'BUY'),
                'total_sell_volume': sum(t.quantity * t.price for t in trades if t.side.value == 'SELL'),
                'average_trade_size': sum(t.quantity * t.price for t in trades) / len(trades) if trades else 0,
                'total_commission': sum(t.commission for t in trades)
            }
        }
        
        if output_file:
            self._save_report(report, output_file)
        
        return report
    
    def _generate_summary(
        self,
        trades: List[Trade],
        positions: List[Position],
        portfolio: Portfolio,
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate summary section."""
        return {
            'total_trades': len(trades),
            'open_positions': len(positions),
            'closed_positions': len([p for p in positions if p.quantity == 0]),
            'total_value': portfolio.calculate_total_value(),
            'cash': portfolio.cash,
            'total_pnl': portfolio.calculate_total_pnl(),
            'total_commission': sum(t.commission for t in trades),
            'winning_trades': len([p for p in positions if p.calculate_pnl() > 0]),
            'losing_trades': len([p for p in positions if p.calculate_pnl() < 0]),
            'win_rate': self._calculate_win_rate(positions)
        }
    
    def _generate_risk_summary(
        self,
        positions: List[Position],
        risk_metrics: Dict[str, Any],
        limits: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate risk summary."""
        total_value = sum(p.quantity * p.current_price for p in positions)
        total_pnl = sum(p.calculate_pnl() for p in positions)
        
        return {
            'total_exposure': total_value,
            'total_pnl': total_pnl,
            'num_positions': len(positions),
            'max_position': max([p.quantity * p.current_price for p in positions]) if positions else 0,
            'var': risk_metrics.get('var', 0),
            'expected_shortfall': risk_metrics.get('expected_shortfall', 0),
            'max_drawdown': risk_metrics.get('max_drawdown', 0),
            'volatility': risk_metrics.get('volatility', 0),
            'limit_breaches': self._check_limit_breaches(risk_metrics, limits)
        }
    
    def _calculate_win_rate(self, positions: List[Position]) -> float:
        """Calculate win rate."""
        if not positions:
            return 0.0
        
        winning = len([p for p in positions if p.calculate_pnl() > 0])
        return winning / len(positions) if positions else 0.0
    
    def _format_trades(self, trades: List[Trade]) -> List[Dict[str, Any]]:
        """Format trades for report."""
        return [
            {
                'order_id': t.order_id,
                'symbol': t.symbol,
                'side': t.side.value,
                'quantity': t.quantity,
                'price': t.price,
                'executed_at': t.executed_at.isoformat() if t.executed_at else None,
                'commission': t.commission,
                'total': t.quantity * t.price
            }
            for t in trades
        ]
    
    def _format_positions(self, positions: List[Position]) -> List[Dict[str, Any]]:
        """Format positions for report."""
        return [
            {
                'symbol': p.symbol,
                'quantity': p.quantity,
                'entry_price': p.entry_price,
                'current_price': p.current_price,
                'pnl': p.calculate_pnl(),
                'pnl_percent': p.calculate_pnl_percent(),
                'entry_time': p.entry_time.isoformat() if p.entry_time else None
            }
            for p in positions
        ]
    
    def _format_portfolio(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Format portfolio for report."""
        return {
            'account_id': portfolio.account_id,
            'cash': portfolio.cash,
            'total_value': portfolio.calculate_total_value(),
            'total_pnl': portfolio.calculate_total_pnl(),
            'num_positions': len(portfolio.positions)
        }
    
    def _generate_charts(
        self,
        trades: List[Trade],
        positions: List[Position],
        portfolio: Portfolio
    ) -> Dict[str, str]:
        """Generate charts and return as base64 images."""
        charts = {}
        
        # PnL distribution chart
        if positions:
            pnl_values = [p.calculate_pnl() for p in positions]
            charts['pnl_distribution'] = self._create_histogram(
                pnl_values,
                title='PnL Distribution',
                xlabel='PnL',
                ylabel='Frequency'
            )
        
        # Position allocation chart
        if positions:
            symbols = [p.symbol for p in positions]
            values = [p.quantity * p.current_price for p in positions]
            charts['position_allocation'] = self._create_pie_chart(
                values,
                labels=symbols,
                title='Position Allocation'
            )
        
        # Performance over time chart
        if trades and trades[0].executed_at:
            dates = [t.executed_at for t in trades if t.executed_at]
            cum_pnl = []
            total = 0
            for t in trades:
                total += t.quantity * t.price
                cum_pnl.append(total)
            charts['cumulative_pnl'] = self._create_line_chart(
                dates,
                cum_pnl,
                title='Cumulative PnL',
                xlabel='Date',
                ylabel='Cumulative PnL'
            )
        
        return charts
    
    def _generate_risk_charts(self, risk_metrics: Dict[str, Any]) -> Dict[str, str]:
        """Generate risk charts."""
        charts = {}
        
        # VaR chart
        if 'var' in risk_metrics:
            charts['var_chart'] = self._create_bar_chart(
                risk_metrics.get('var_history', []),
                title='Value at Risk Over Time',
                xlabel='Time',
                ylabel='VaR'
            )
        
        return charts
    
    def _check_limit_breaches(
        self,
        risk_metrics: Dict[str, Any],
        limits: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for risk limit breaches."""
        breaches = []
        
        for key, value in risk_metrics.items():
            if key in limits:
                if value > limits[key]:
                    breaches.append({
                        'metric': key,
                        'value': value,
                        'limit': limits[key],
                        'breach_percent': (value / limits[key]) - 1
                    })
        
        return breaches
    
    def _get_period(self, positions: List[Position]) -> Dict[str, Any]:
        """Get report period."""
        if not positions:
            return {'start': None, 'end': None, 'duration': None}
        
        times = [p.entry_time for p in positions if p.entry_time]
        if not times:
            return {'start': None, 'end': None, 'duration': None}
        
        start = min(times)
        end = max(times)
        duration = end - start if start and end else None
        
        return {
            'start': start.isoformat() if start else None,
            'end': end.isoformat() if end else None,
            'duration': str(duration) if duration else None
        }
    
    def _save_report(self, report: Dict[str, Any], output_file: str) -> None:
        """Save report to file."""
        output_path = self.output_dir / output_file
        
        # Determine format from extension
        extension = output_path.suffix.lower()
        
        if extension == '.json':
            self._save_json_report(report, output_path)
        elif extension == '.csv':
            self._save_csv_report(report, output_path)
        elif extension == '.html':
            self._save_html_report(report, output_path)
        elif extension == '.yaml' or extension == '.yml':
            self._save_yaml_report(report, output_path)
        elif extension == '.xlsx':
            self._save_excel_report(report, output_path)
        else:
            # Default to JSON
            self._save_json_report(report, output_path.with_suffix('.json'))
    
    def _save_json_report(self, report: Dict[str, Any], path: Path) -> None:
        """Save report as JSON."""
        with open(path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
    
    def _save_yaml_report(self, report: Dict[str, Any], path: Path) -> None:
        """Save report as YAML."""
        with open(path, 'w') as f:
            yaml.dump(report, f, default_flow_style=False)
    
    def _save_csv_report(self, report: Dict[str, Any], path: Path) -> None:
        """Save report as CSV."""
        # Extract tabular data
        if 'trades' in report and report['trades']:
            df = pd.DataFrame(report['trades'])
            df.to_csv(path, index=False)
        elif 'positions' in report and report['positions']:
            df = pd.DataFrame(report['positions'])
            df.to_csv(path, index=False)
        else:
            # Create a summary CSV
            summary = report.get('summary', {})
            df = pd.DataFrame([summary])
            df.to_csv(path, index=False)
    
    def _save_html_report(self, report: Dict[str, Any], path: Path) -> None:
        """Save report as HTML."""
        template = self._get_html_template()
        html = template.render(report=report)
        with open(path, 'w') as f:
            f.write(html)
    
    def _save_excel_report(self, report: Dict[str, Any], path: Path) -> None:
        """Save report as Excel."""
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            # Summary sheet
            summary = report.get('summary', {})
            pd.DataFrame([summary]).to_excel(writer, sheet_name='Summary', index=False)
            
            # Trades sheet
            if 'trades' in report and report['trades']:
                pd.DataFrame(report['trades']).to_excel(writer, sheet_name='Trades', index=False)
            
            # Positions sheet
            if 'positions' in report and report['positions']:
                pd.DataFrame(report['positions']).to_excel(writer, sheet_name='Positions', index=False)
            
            # Metrics sheet
            if 'metrics' in report:
                metrics = report['metrics']
                pd.DataFrame([metrics]).to_excel(writer, sheet_name='Metrics', index=False)
    
    def _get_html_template(self) -> Template:
        """Get HTML template for reports."""
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NEXUS Trading Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1, h2 { color: #2c3e50; }
                table { border-collapse: collapse; width: 100%; margin: 10px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #3498db; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .summary-box { background-color: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px; padding: 10px; background-color: #ecf0f1; border-radius: 5px; }
                .metric-label { font-weight: bold; }
                .metric-value { font-size: 24px; color: #2c3e50; }
                .positive { color: #27ae60; }
                .negative { color: #e74c3c; }
            </style>
        </head>
        <body>
            <h1>NEXUS Trading Report</h1>
            <p>Generated: {{ report.timestamp }}</p>
            
            <h2>Summary</h2>
            <div class="summary-box">
                {% for key, value in report.summary.items() %}
                <div class="metric">
                    <div class="metric-label">{{ key|replace('_', ' ')|title }}</div>
                    <div class="metric-value">{{ value }}</div>
                </div>
                {% endfor %}
            </div>
            
            {% if report.trades %}
            <h2>Trades ({{ report.trades|length }})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Order ID</th>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Quantity</th>
                        <th>Price</th>
                        <th>Commission</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for trade in report.trades %}
                    <tr>
                        <td>{{ trade.order_id }}</td>
                        <td>{{ trade.symbol }}</td>
                        <td>{{ trade.side }}</td>
                        <td>{{ trade.quantity }}</td>
                        <td>{{ trade.price }}</td>
                        <td>{{ trade.commission }}</td>
                        <td>{{ trade.total }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            
            {% if report.positions %}
            <h2>Positions ({{ report.positions|length }})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Quantity</th>
                        <th>Entry Price</th>
                        <th>Current Price</th>
                        <th>PnL</th>
                        <th>PnL %</th>
                    </tr>
                </thead>
                <tbody>
                    {% for pos in report.positions %}
                    <tr>
                        <td>{{ pos.symbol }}</td>
                        <td>{{ pos.quantity }}</td>
                        <td>{{ pos.entry_price }}</td>
                        <td>{{ pos.current_price }}</td>
                        <td class="{% if pos.pnl > 0 %}positive{% else %}negative{% endif %}">{{ pos.pnl }}</td>
                        <td class="{% if pos.pnl_percent > 0 %}positive{% else %}negative{% endif %}">{{ pos.pnl_percent }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            
            {% if report.metrics %}
            <h2>Performance Metrics</h2>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {% for key, value in report.metrics.items() %}
                    <tr>
                        <td>{{ key|replace('_', ' ')|title }}</td>
                        <td>{{ value }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            
            {% if report.charts %}
            <h2>Charts</h2>
            {% for name, chart in report.charts.items() %}
            <div>
                <h3>{{ name|replace('_', ' ')|title }}</h3>
                <img src="data:image/png;base64,{{ chart }}" style="max-width: 100%;">
            </div>
            {% endfor %}
            {% endif %}
        </body>
        </html>
        """
        return Template(template_str)
    
    def _create_histogram(
        self,
        data: List[float],
        title: str = 'Histogram',
        xlabel: str = 'Value',
        ylabel: str = 'Frequency'
    ) -> str:
        """Create a histogram chart."""
        plt.figure(figsize=(8, 6))
        plt.hist(data, bins=20, alpha=0.7, color='#3498db', edgecolor='black')
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.3)
        
        return self._figure_to_base64()
    
    def _create_pie_chart(
        self,
        values: List[float],
        labels: List[str],
        title: str = 'Pie Chart'
    ) -> str:
        """Create a pie chart."""
        plt.figure(figsize=(8, 8))
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
        plt.title(title)
        plt.axis('equal')
        
        return self._figure_to_base64()
    
    def _create_line_chart(
        self,
        x: List,
        y: List[float],
        title: str = 'Line Chart',
        xlabel: str = 'X',
        ylabel: str = 'Y'
    ) -> str:
        """Create a line chart."""
        plt.figure(figsize=(10, 6))
        plt.plot(x, y, linewidth=2, color='#2ecc71')
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.3)
        
        return self._figure_to_base64()
    
    def _create_bar_chart(
        self,
        data: List[float],
        title: str = 'Bar Chart',
        xlabel: str = 'X',
        ylabel: str = 'Y'
    ) -> str:
        """Create a bar chart."""
        plt.figure(figsize=(10, 6))
        plt.bar(range(len(data)), data, color='#e74c3c', alpha=0.7)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.3)
        
        return self._figure_to_base64()
    
    def _figure_to_base64(self) -> str:
        """Convert matplotlib figure to base64 string."""
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        return image_base64


# Utility functions
def generate_report(
    trades: List[Trade],
    positions: List[Position],
    portfolio: Portfolio,
    metrics: Dict[str, Any],
    output_file: Optional[str] = None,
    report_type: str = 'performance'
) -> Dict[str, Any]:
    """
    Generate a report.
    
    Args:
        trades: List of trades
        positions: List of positions
        portfolio: Portfolio data
        metrics: Performance metrics
        output_file: Output file name
        report_type: Type of report ('performance', 'risk', 'daily', 'trade')
    
    Returns:
        Report data
    """
    generator = ReportGenerator()
    
    if report_type == 'performance':
        return generator.generate_performance_report(trades, positions, portfolio, metrics, output_file)
    elif report_type == 'risk':
        return generator.generate_risk_report(positions, metrics, {}, output_file)
    elif report_type == 'daily':
        return generator.generate_daily_report(trades, positions, portfolio, metrics, output_file)
    elif report_type == 'trade':
        return generator.generate_trade_report(trades, output_file)
    else:
        raise ValueError(f"Unknown report type: {report_type}")


__all__ = [
    'ReportGenerator',
    'generate_report'
]

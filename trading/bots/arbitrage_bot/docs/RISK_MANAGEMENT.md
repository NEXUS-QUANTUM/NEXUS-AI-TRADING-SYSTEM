# NEXUS AI Trading System - Risk Management Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Principes de Gestion des Risques](#principes-de-gestion-des-risques)
3. [Types de Risques](#types-de-risques)
4. [Position Sizing](#position-sizing)
5. [Stop Loss et Take Profit](#stop-loss-et-take-profit)
6. [Drawdown Management](#drawdown-management)
7. [Circuit Breaker](#circuit-breaker)
8. [VaR et CVaR](#var-et-cvar)
9. [Stress Testing](#stress-testing)
10. [Portfolio Risk](#portfolio-risk)
11. [Risk Monitoring](#risk-monitoring)
12. [Risk Reporting](#risk-reporting)
13. [Configuration](#configuration)
14. [Exemples](#exemples)

---

## Introduction

La gestion des risques est un élément fondamental du NEXUS AI Trading System. Ce guide détaille les mécanismes de gestion des risques intégrés pour protéger votre capital et optimiser les performances.

### Objectifs de la Gestion des Risques

1. **Protection du Capital**: Limiter les pertes maximales
2. **Optimisation des Rendements**: Maximiser le ratio risque/rendement
3. **Stabilité**: Maintenir une performance cohérente
4. **Survie**: Assurer la pérennité du système

---

## Principes de Gestion des Risques

### Règles d'Or

```yaml
risk_principles:
  # 1. Ne jamais risquer plus que ce que vous pouvez perdre
  max_loss_per_trade: 0.02  # 2% du capital
  max_loss_per_day: 0.05    # 5% du capital
  max_loss_per_week: 0.10   # 10% du capital
  
  # 2. Diversification
  max_position_per_asset: 0.20  # 20% du capital
  max_position_per_exchange: 0.30  # 30% du capital
  
  # 3. Gestion des émotions
  emotion_control: true
  max_trades_per_day: 50
  cooldown_after_loss: 3600  # 1 heure
  
  # 4. Planification
  trading_plan: true
  risk_reward_ratio: 2.0
  max_drawdown: 0.15  # 15%
```

---

## Types de Risques

### Risques de Marché

```yaml
market_risks:
  volatility_risk:
    enabled: true
    max_volatility: 0.30  # 30% de volatilité annuelle
    volatility_adjustment: true
  
  liquidity_risk:
    enabled: true
    min_liquidity: 100000  # USD
    max_slippage: 0.01  # 1%
    min_order_book_depth: 10
  
  gap_risk:
    enabled: true
    max_gap: 0.05  # 5%
    gap_protection: true
```

### Risques Opérationnels

```yaml
operational_risks:
  technical_risk:
    enabled: true
    max_downtime: 300  # secondes
    failover_enabled: true
    redundancy: true
  
  execution_risk:
    enabled: true
    max_execution_time: 30  # secondes
    retry_attempts: 3
    max_slippage: 0.005  # 0.5%
  
  connectivity_risk:
    enabled: true
    heartbeat_interval: 10  # secondes
    reconnect_attempts: 5
    backup_connection: true
```

### Risques de Contrepartie

```yaml
counterparty_risks:
  exchange_risk:
    enabled: true
    max_exposure: 1000000  # USD
    exchange_rating: "A"
    diversification: true
  
  broker_risk:
    enabled: true
    max_exposure: 500000  # USD
    broker_rating: "A"
    regulation: "FCA"
```

---

## Position Sizing

### Stratégies de Dimensionnement

```yaml
position_sizing:
  # 1. Fixed Size
  fixed:
    enabled: true
    size: 1000  # USD
    min_size: 100
    max_size: 50000
  
  # 2. Kelly Criterion
  kelly:
    enabled: true
    fraction: 0.25
    min_fraction: 0.10
    max_fraction: 0.50
    calculate_auto: true
  
  # 3. Volatility-Based
  volatility:
    enabled: true
    lookback: 20  # jours
    multiplier: 0.5
    max_volatility: 1.0
    min_volatility: 0.1
  
  # 4. Risk-Based
  risk_based:
    enabled: true
    risk_per_trade: 0.01  # 1%
    max_risk_per_day: 0.05  # 5%
    risk_adjustment: 0.5
  
  # 5. Adaptive
  adaptive:
    enabled: true
    momentum_factor: 0.3
    volatility_factor: 0.4
    correlation_factor: 0.3
    lookback_period: 60  # jours
```

### Exemple de Calcul

```python
def calculate_position_size(capital, risk_percent, stop_loss_percent):
    """
    Calcule la taille de position
    
    Args:
        capital: Capital total
        risk_percent: Risque en pourcentage
        stop_loss_percent: Stop loss en pourcentage
    
    Returns:
        float: Taille de position
    """
    risk_amount = capital * risk_percent
    position_size = risk_amount / stop_loss_percent
    return position_size

# Exemple
capital = 10000
risk_percent = 0.01  # 1%
stop_loss_percent = 0.02  # 2%

position_size = calculate_position_size(capital, risk_percent, stop_loss_percent)
# position_size = 5000 (USD)
```

---

## Stop Loss et Take Profit

### Stop Loss

```yaml
stop_loss:
  # 1. Fixed Stop Loss
  fixed:
    enabled: true
    percentage: 0.02  # 2%
    max_percentage: 0.05  # 5%
  
  # 2. Trailing Stop Loss
  trailing:
    enabled: true
    activation: 0.01  # 1%
    offset: 0.01  # 1%
    max_offset: 0.05  # 5%
    min_offset: 0.005  # 0.5%
  
  # 3. Dynamic Stop Loss
  dynamic:
    enabled: true
    volatility_multiplier: 1.5
    atr_period: 14
    atr_multiplier: 2.0
    max_dynamic: 0.08  # 8%
  
  # 4. Volatility-Based
  volatility_based:
    enabled: true
    lookback: 20  # jours
    multiplier: 2.0
    max_stop: 0.06  # 6%
  
  # 5. Time-Based
  time_based:
    enabled: true
    max_position_duration: 86400  # 24 heures
    partial_close: true
    partial_percentage: 0.50  # 50%
```

### Take Profit

```yaml
take_profit:
  # 1. Fixed Take Profit
  fixed:
    enabled: true
    percentage: 0.03  # 3%
    max_percentage: 0.10  # 10%
  
  # 2. Multiple Targets
  multiple:
    enabled: true
    levels:
      - percentage: 0.01  # 1%
        allocation: 0.20  # 20%
      - percentage: 0.02  # 2%
        allocation: 0.20  # 20%
      - percentage: 0.03  # 3%
        allocation: 0.20  # 20%
      - percentage: 0.05  # 5%
        allocation: 0.20  # 20%
      - percentage: 0.08  # 8%
        allocation: 0.20  # 20%
  
  # 3. Trailing Take Profit
  trailing:
    enabled: true
    activation: 0.02  # 2%
    offset: 0.01  # 1%
    max_offset: 0.05  # 5%
  
  # 4. Dynamic
  dynamic:
    enabled: true
    volatility_multiplier: 2.0
    atr_period: 14
    atr_multiplier: 3.0
    max_dynamic: 0.12  # 12%
```

### Risk-Reward Ratio

```yaml
risk_reward:
  enabled: true
  min_ratio: 1.5
  max_ratio: 5.0
  default_ratio: 2.0
  adaptive: true
  
  # Calcul automatique
  calculate: true
  min_stop_loss: 0.01
  max_stop_loss: 0.05
  min_take_profit: 0.02
  max_take_profit: 0.15
```

---

## Drawdown Management

### Configurations

```yaml
drawdown:
  # 1. Maximum Drawdown
  max_drawdown:
    daily: 0.05  # 5%
    weekly: 0.10  # 10%
    monthly: 0.15  # 15%
    quarterly: 0.20  # 20%
    yearly: 0.25  # 25%
    max_absolute: 0.30  # 30%
  
  # 2. Recovery
  recovery:
    min_recovery: 0.02  # 2%
    max_recovery_time: 604800  # 7 jours
    recovery_action: "reduce"
  
  # 3. Protection
  protection:
    enabled: true
    type: "dynamic"
    max_position_reduction: 0.50
    reduction_speed: 0.10
    recovery_speed: 0.05
  
  # 4. Monitoring
  monitoring:
    check_interval: 60  # secondes
    alert_threshold: 0.03  # 3%
    critical_threshold: 0.05  # 5%
```

### Exemple de Calcul

```python
def calculate_drawdown(equity_curve):
    """
    Calcule le drawdown
    
    Args:
        equity_curve: Liste des valeurs d'équité
    
    Returns:
        float: Drawdown maximum
    """
    peak = equity_curve[0]
    drawdown = 0
    
    for value in equity_curve:
        if value > peak:
            peak = value
        current_drawdown = (peak - value) / peak
        if current_drawdown > drawdown:
            drawdown = current_drawdown
    
    return drawdown

# Exemple
equity_curve = [100, 110, 120, 115, 105, 100, 95]
drawdown = calculate_drawdown(equity_curve)
# drawdown = 0.208 (20.8%)
```

---

## Circuit Breaker

### Configuration

```yaml
circuit_breaker:
  # 1. General Settings
  general:
    failure_threshold: 5
    failure_window: 60  # secondes
    cooldown_period: 300  # secondes
    max_failures_per_hour: 20
    max_failures_per_day: 100
  
  # 2. Types
  types:
    exchange:
      enabled: true
      failure_threshold: 3
      cooldown_period: 600  # secondes
    
    strategy:
      enabled: true
      failure_threshold: 3
      cooldown_period: 900  # secondes
    
    pair:
      enabled: true
      failure_threshold: 2
      cooldown_period: 600  # secondes
    
    system:
      enabled: true
      failure_threshold: 5
      cooldown_period: 3600  # secondes
  
  # 3. Recovery
  recovery:
    enabled: true
    half_open_timeout: 60  # secondes
    success_threshold: 3
    failure_retry_count: 2
  
  # 4. Monitoring
  monitoring:
    enabled: true
    alert_on_trip: true
    alert_on_recovery: true
    log_trips: true
```

---

## VaR et CVaR

### Calcul de VaR

```yaml
var:
  # 1. Historical VaR
  historical:
    enabled: true
    confidence_level: 0.95
    time_horizon: 1  # jour
    lookback_period: 365  # jours
  
  # 2. Monte Carlo VaR
  monte_carlo:
    enabled: true
    confidence_level: 0.95
    time_horizon: 1  # jour
    simulations: 10000
  
  # 3. Parametric VaR
  parametric:
    enabled: true
    confidence_level: 0.95
    time_horizon: 1  # jour
    distribution: "normal"
  
  # 4. CVaR
  cvar:
    enabled: true
    confidence_level: 0.95
    time_horizon: 1  # jour
    max_cvar: 0.08  # 8%
```

### Exemple de Calcul

```python
import numpy as np
from scipy import stats

def calculate_var(returns, confidence_level=0.95):
    """
    Calcule la VaR
    
    Args:
        returns: Liste des rendements
        confidence_level: Niveau de confiance
    
    Returns:
        float: VaR
    """
    sorted_returns = np.sort(returns)
    index = int((1 - confidence_level) * len(sorted_returns))
    var = -sorted_returns[index]
    return var

# Exemple
returns = np.random.normal(0, 0.02, 1000)
var_95 = calculate_var(returns, 0.95)
# var_95 = 0.0328 (3.28%)
```

---

## Stress Testing

### Scénarios

```yaml
stress_testing:
  scenarios:
    # 1. Financial Crisis
    - name: "2008_financial_crisis"
      description: "2008 financial crisis scenario"
      market_drop: 0.40  # 40%
      volatility_spike: 2.0
      liquidity_drop: 0.50
    
    # 2. COVID-19 Crash
    - name: "2020_covid_crash"
      description: "COVID-19 crash scenario"
      market_drop: 0.30
      volatility_spike: 1.5
      liquidity_drop: 0.30
    
    # 3. Crypto Crash
    - name: "crypto_crash"
      description: "Cryptocurrency crash"
      market_drop: 0.70
      volatility_spike: 3.0
      liquidity_drop: 0.70
    
    # 4. Flash Crash
    - name: "flash_crash"
      description: "Flash crash scenario"
      market_drop: 0.50
      volatility_spike: 2.5
      liquidity_drop: 0.80
    
    # 5. Liquidity Crisis
    - name: "liquidity_crisis"
      description: "Liquidity crisis"
      market_drop: 0.20
      volatility_spike: 1.2
      liquidity_drop: 0.90
  
  parameters:
    time_horizon: 30  # jours
    confidence_level: 0.99
    monte_carlo_simulations: 10000
    historical_lookback: 365  # jours
  
  reporting:
    enabled: true
    format: "pdf"
    include_detailed: true
    include_summary: true
```

---

## Portfolio Risk

### Diversification

```yaml
diversification:
  enabled: true
  max_correlation: 0.70
  max_concentration: 0.20
  min_assets: 5
  max_assets: 20
  
  correlation:
    enabled: true
    lookback_period: 60
    calculation_frequency: 3600
    threshold: 0.70
    hedging_enabled: true
  
  beta:
    enabled: true
    benchmark: "BTC/USDT"
    max_beta: 1.5
    min_beta: -0.5
    beta_hedging: true
```

### Exemple de Calcul

```python
def calculate_portfolio_risk(positions, correlation_matrix):
    """
    Calcule le risque du portefeuille
    
    Args:
        positions: Liste des positions
        correlation_matrix: Matrice de corrélation
    
    Returns:
        float: Risque du portefeuille
    """
    weights = [p['weight'] for p in positions]
    volatilities = [p['volatility'] for p in positions]
    
    portfolio_variance = 0
    for i in range(len(weights)):
        for j in range(len(weights)):
            portfolio_variance += (
                weights[i] * weights[j] * 
                volatilities[i] * volatilities[j] * 
                correlation_matrix[i][j]
            )
    
    portfolio_risk = np.sqrt(portfolio_variance)
    return portfolio_risk
```

---

## Risk Monitoring

### Métriques

```yaml
monitoring:
  metrics:
    # Performance
    performance:
      - "sharpe_ratio"
      - "sortino_ratio"
      - "calmar_ratio"
      - "omega_ratio"
      - "sterling_ratio"
      - "burke_ratio"
      - "martin_ratio"
    
    # Risk
    risk:
      - "var"
      - "cvar"
      - "expected_shortfall"
      - "maximum_drawdown"
      - "average_drawdown"
      - "drawdown_duration"
      - "ulcer_index"
    
    # Trading
    trading:
      - "win_rate"
      - "loss_rate"
      - "profit_factor"
      - "average_win"
      - "average_loss"
      - "win_loss_ratio"
      - "expectancy"
      - "risk_reward_ratio"
  
  calculation:
    frequency: 3600
    lookback_period: 365
    min_data_points: 30
    max_data_points: 1000
```

### Dashboard

```yaml
dashboard:
  enabled: true
  refresh_interval: 10
  
  panels:
    - "pnl"
    - "drawdown"
    - "risk_metrics"
    - "positions"
    - "trades"
    - "performance"
    - "stress_test"
```

---

## Risk Reporting

### Types de Rapports

```yaml
reporting:
  # 1. Daily Report
  daily:
    enabled: true
    schedule: "0 0 * * *"
    format: "pdf"
    content:
      - "summary"
      - "drawdown_analysis"
      - "var_analysis"
      - "position_report"
      - "risk_metrics"
  
  # 2. Weekly Report
  weekly:
    enabled: true
    schedule: "0 0 * * 0"
    format: "pdf"
    content:
      - "summary"
      - "drawdown_analysis"
      - "var_analysis"
      - "correlation_analysis"
      - "performance_metrics"
      - "position_report"
      - "risk_metrics"
  
  # 3. Monthly Report
  monthly:
    enabled: true
    schedule: "0 0 1 * *"
    format: "pdf"
    content:
      - "summary"
      - "drawdown_analysis"
      - "var_analysis"
      - "correlation_analysis"
      - "performance_metrics"
      - "position_report"
      - "risk_metrics"
      - "scenario_analysis"
      - "stress_test_results"
  
  # 4. Compliance Report
  compliance:
    enabled: true
    schedule: "0 0 1 */3 *"
    format: "pdf"
    content:
      - "summary"
      - "compliance_metrics"
      - "regulatory_limits"
      - "audit_trail"
  
  distribution:
    enabled: true
    email:
      - "risk@nexustradingia.com"
      - "compliance@nexustradingia.com"
      - "management@nexustradingia.com"
    storage:
      enabled: true
      path: "s3://${REPORT_BUCKET}/risk_reports/"
      retention: 90  # jours
```

---

## Configuration

### Fichier de Configuration

```yaml
# config/risk_config.yaml
risk_management:
  enabled: true
  
  # Position Sizing
  position_sizing:
    strategy: "adaptive"
    max_position_size: 50000
    min_position_size: 100
    kelly_fraction: 0.25
  
  # Stop Loss
  stop_loss:
    enabled: true
    type: "trailing"
    percentage: 0.02
    trailing_offset: 0.01
  
  # Take Profit
  take_profit:
    enabled: true
    type: "multiple"
    targets:
      - 0.01
      - 0.02
      - 0.03
      - 0.05
    allocation:
      - 0.25
      - 0.25
      - 0.25
      - 0.25
  
  # Drawdown
  drawdown:
    max_drawdown: 0.15
    daily_loss_limit: 0.05
    weekly_loss_limit: 0.10
  
  # Circuit Breaker
  circuit_breaker:
    enabled: true
    consecutive_failures: 5
    cooldown_period: 300
  
  # VaR
  var:
    confidence_level: 0.95
    time_horizon: 1
    max_var: 0.05
  
  # Monitoring
  monitoring:
    enabled: true
    check_interval: 10
    alert_threshold: 0.03
  
  # Reporting
  reporting:
    enabled: true
    interval: "daily"
    format: "pdf"
```

---

## Exemples

### Exemple Complet

```python
from trading.bots.arbitrage_bot import ArbitrageBot
from trading.bots.arbitrage_bot.risk import RiskManager

# Créer le bot
bot = ArbitrageBot(config_path="config/arbitrage_config.yaml")

# Configurer les risques
risk_config = {
    'max_drawdown': 0.15,
    'daily_loss_limit': 0.05,
    'position_sizing': {
        'strategy': 'adaptive',
        'max_position_size': 50000,
        'min_position_size': 100,
    },
    'stop_loss': {
        'enabled': True,
        'type': 'trailing',
        'percentage': 0.02,
    },
    'take_profit': {
        'enabled': True,
        'type': 'multiple',
        'targets': [0.01, 0.02, 0.03, 0.05],
        'allocation': [0.25, 0.25, 0.25, 0.25],
    },
    'circuit_breaker': {
        'enabled': True,
        'consecutive_failures': 5,
        'cooldown_period': 300,
    },
    'var': {
        'confidence_level': 0.95,
        'time_horizon': 1,
        'max_var': 0.05,
    },
    'monitoring': {
        'enabled': True,
        'check_interval': 10,
        'alert_threshold': 0.03,
    },
    'reporting': {
        'enabled': True,
        'interval': 'daily',
        'format': 'pdf',
    },
}

# Appliquer la configuration
bot.configure_risk(risk_config)

# Démarrer le bot
bot.start()

# Monitorer les risques
risk_report = bot.get_risk_report()
print(risk_report)

# Arrêter le bot
bot.stop()
```

---

## 📚 Ressources Additionnelles

- [Guide de Configuration](CONFIGURATION.md)
- [Guide des Stratégies](STRATEGIES.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Référence API](API.md)
- [FAQ](FAQ.md)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter:

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

"""
NEXUS AI TRADING SYSTEM - HEDGE BOT HELPERS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'helpers pour le Hedge Bot.
Fonctions utilitaires pour les calculs, conversions, validations, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import json
import logging
import math
import random
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache, wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


# ============================================================================
# DECORATEURS
# ============================================================================

def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple = (Exception,),
    logger_obj: Optional[logging.Logger] = None
) -> Callable:
    """
    Décorateur pour retenter une fonction en cas d'erreur.

    Args:
        max_retries: Nombre maximum de tentatives
        delay: Délai initial
        backoff: Multiplicateur de délai
        exceptions: Exceptions à capturer
        logger_obj: Logger à utiliser

    Returns:
        Fonction décorée
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            _logger = logger_obj or logger
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        _logger.warning(
                            f"Tentative {attempt + 1}/{max_retries} échouée pour {func.__name__}: {e}. "
                            f"Nouvelle tentative dans {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        _logger.error(
                            f"Toutes les tentatives ({max_retries}) ont échoué pour {func.__name__}: {e}"
                        )
            
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            _logger = logger_obj or logger
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        _logger.warning(
                            f"Tentative {attempt + 1}/{max_retries} échouée pour {func.__name__}: {e}. "
                            f"Nouvelle tentative dans {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        _logger.error(
                            f"Toutes les tentatives ({max_retries}) ont échoué pour {func.__name__}: {e}"
                        )
            
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def timed_cache(seconds: int = 300, maxsize: int = 128) -> Callable:
    """
    Décorateur pour mettre en cache les résultats d'une fonction avec expiration.

    Args:
        seconds: Durée de vie du cache en secondes
        maxsize: Taille maximale du cache

    Returns:
        Fonction décorée
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        timestamps = {}

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = hashlib.md5(
                f"{args}{kwargs}".encode('utf-8')
            ).hexdigest()
            
            now = time.time()
            if key in cache and (now - timestamps.get(key, 0)) < seconds:
                return cache[key]
            
            result = await func(*args, **kwargs)
            cache[key] = result
            timestamps[key] = now
            
            # Nettoyage si le cache est trop grand
            if len(cache) > maxsize:
                oldest = sorted(timestamps.items(), key=lambda x: x[1])[0]
                del cache[oldest[0]]
                del timestamps[oldest[0]]
            
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = hashlib.md5(
                f"{args}{kwargs}".encode('utf-8')
            ).hexdigest()
            
            now = time.time()
            if key in cache and (now - timestamps.get(key, 0)) < seconds:
                return cache[key]
            
            result = func(*args, **kwargs)
            cache[key] = result
            timestamps[key] = now
            
            if len(cache) > maxsize:
                oldest = sorted(timestamps.items(), key=lambda x: x[1])[0]
                del cache[oldest[0]]
                del timestamps[oldest[0]]
            
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def async_to_sync(func: Callable) -> Callable:
    """
    Convertit une fonction asynchrone en synchrone.

    Args:
        func: Fonction asynchrone

    Returns:
        Fonction synchrone
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(func(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# ============================================================================
# CALCULS MATHÉMATIQUES
# ============================================================================

def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02
) -> float:
    """
    Calcule le Sharpe Ratio.

    Args:
        returns: Liste des rendements
        risk_free_rate: Taux sans risque

    Returns:
        Sharpe Ratio
    """
    if not returns:
        return 0.0
    
    avg_return = np.mean(returns)
    std_return = np.std(returns)
    
    if std_return == 0:
        return 0.0
    
    daily_rf = risk_free_rate / 365
    sharpe = (avg_return - daily_rf) / std_return
    
    return sharpe * np.sqrt(365)


def calculate_sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02
) -> float:
    """
    Calcule le Sortino Ratio.

    Args:
        returns: Liste des rendements
        risk_free_rate: Taux sans risque

    Returns:
        Sortino Ratio
    """
    if not returns:
        return 0.0
    
    avg_return = np.mean(returns)
    downside_returns = [r for r in returns if r < 0]
    
    if not downside_returns:
        return 0.0
    
    downside_deviation = np.std(downside_returns)
    if downside_deviation == 0:
        return 0.0
    
    daily_rf = risk_free_rate / 365
    sortino = (avg_return - daily_rf) / downside_deviation
    
    return sortino * np.sqrt(365)


def calculate_calmar_ratio(
    returns: List[float],
    max_drawdown: Optional[float] = None
) -> float:
    """
    Calcule le Calmar Ratio.

    Args:
        returns: Liste des rendements
        max_drawdown: Drawdown maximum

    Returns:
        Calmar Ratio
    """
    if not returns:
        return 0.0
    
    annualized_return = calculate_annualized_return(returns)
    
    if max_drawdown is None:
        max_drawdown = calculate_max_drawdown(returns)
    
    if max_drawdown == 0:
        return 0.0
    
    return annualized_return / (max_drawdown / 100)


def calculate_annualized_return(returns: List[float]) -> float:
    """
    Calcule le rendement annualisé.

    Args:
        returns: Liste des rendements

    Returns:
        Rendement annualisé
    """
    if not returns:
        return 0.0
    
    total_return = calculate_total_return(returns) / 100
    n = len(returns)
    days = n
    
    if days > 0:
        annualized = (1 + total_return) ** (365 / days) - 1
        return annualized * 100
    
    return 0.0


def calculate_total_return(returns: List[float]) -> float:
    """
    Calcule le rendement total.

    Args:
        returns: Liste des rendements

    Returns:
        Rendement total
    """
    if not returns:
        return 0.0
    
    cumulative = 1.0
    for r in returns:
        cumulative *= (1 + r)
    
    return (cumulative - 1) * 100


def calculate_max_drawdown(returns: List[float]) -> float:
    """
    Calcule le maximum drawdown.

    Args:
        returns: Liste des rendements

    Returns:
        Maximum drawdown
    """
    if not returns:
        return 0.0
    
    cumulative = np.cumprod(1 + np.array(returns))
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    max_dd = np.min(drawdown)
    
    return abs(max_dd) * 100


def calculate_var(
    returns: List[float],
    confidence: float = 0.95
) -> float:
    """
    Calcule la Value at Risk.

    Args:
        returns: Liste des rendements
        confidence: Niveau de confiance

    Returns:
        VaR
    """
    if not returns:
        return 0.0
    
    var_percentile = (1 - confidence) * 100
    var = np.percentile(returns, var_percentile)
    
    return abs(var) * 100


def calculate_expected_shortfall(returns: List[float]) -> float:
    """
    Calcule l'Expected Shortfall.

    Args:
        returns: Liste des rendements

    Returns:
        Expected Shortfall
    """
    if not returns:
        return 0.0
    
    var_95 = calculate_var(returns, 0.95) / 100
    tail_returns = [r for r in returns if r < var_95]
    
    if not tail_returns:
        return 0.0
    
    es = np.mean(tail_returns)
    return abs(es) * 100


def calculate_profit_factor(
    trades: List[Dict[str, Any]],
    profit_key: str = "profit"
) -> float:
    """
    Calcule le Profit Factor.

    Args:
        trades: Liste des transactions
        profit_key: Clé du profit

    Returns:
        Profit Factor
    """
    if not trades:
        return 0.0
    
    gross_profit = sum(
        t.get(profit_key, 0) for t in trades if t.get(profit_key, 0) > 0
    )
    gross_loss = abs(sum(
        t.get(profit_key, 0) for t in trades if t.get(profit_key, 0) < 0
    ))
    
    if gross_loss == 0:
        return float('inf')
    
    return gross_profit / gross_loss


def calculate_win_rate(trades: List[Dict[str, Any]]) -> float:
    """
    Calcule le taux de victoire.

    Args:
        trades: Liste des transactions

    Returns:
        Taux de victoire
    """
    if not trades:
        return 0.0
    
    wins = sum(1 for t in trades if t.get("profit", 0) > 0)
    return wins / len(trades)


def calculate_risk_reward_ratio(trades: List[Dict[str, Any]]) -> float:
    """
    Calcule le ratio risque/récompense.

    Args:
        trades: Liste des transactions

    Returns:
        Ratio risque/récompense
    """
    wins = [t.get("profit", 0) for t in trades if t.get("profit", 0) > 0]
    losses = [abs(t.get("profit", 0)) for t in trades if t.get("profit", 0) < 0]
    
    if not wins or not losses:
        return 0.0
    
    avg_win = np.mean(wins)
    avg_loss = np.mean(losses)
    
    if avg_loss == 0:
        return 0.0
    
    return avg_win / avg_loss


def calculate_beta(
    asset_returns: List[float],
    market_returns: List[float]
) -> float:
    """
    Calcule le Beta.

    Args:
        asset_returns: Rendements de l'actif
        market_returns: Rendements du marché

    Returns:
        Beta
    """
    if len(asset_returns) != len(market_returns) or not asset_returns:
        return 1.0
    
    covariance = np.cov(asset_returns, market_returns)[0][1]
    variance = np.var(market_returns)
    
    if variance == 0:
        return 1.0
    
    return covariance / variance


def calculate_alpha(
    asset_returns: List[float],
    market_returns: List[float],
    risk_free_rate: float = 0.02
) -> float:
    """
    Calcule l'Alpha.

    Args:
        asset_returns: Rendements de l'actif
        market_returns: Rendements du marché
        risk_free_rate: Taux sans risque

    Returns:
        Alpha
    """
    if not asset_returns or not market_returns:
        return 0.0
    
    asset_avg = np.mean(asset_returns)
    market_avg = np.mean(market_returns)
    beta = calculate_beta(asset_returns, market_returns)
    
    daily_rf = risk_free_rate / 365
    alpha = asset_avg - (daily_rf + beta * (market_avg - daily_rf))
    
    return alpha * 365 * 100


def calculate_volatility(
    prices: List[float],
    annualize: bool = True
) -> float:
    """
    Calcule la volatilité.

    Args:
        prices: Liste des prix
        annualize: Annualiser

    Returns:
        Volatilité
    """
    if len(prices) < 2:
        return 0.0
    
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
    
    if not returns:
        return 0.0
    
    volatility = np.std(returns)
    
    if annualize:
        volatility *= np.sqrt(365)
    
    return volatility * 100


# ============================================================================
# CALCULS DE POSITION
# ============================================================================

def calculate_position_size(
    account_equity: Decimal,
    risk_per_trade: float,
    entry_price: Decimal,
    stop_loss: Decimal,
    leverage: float = 1.0
) -> Decimal:
    """
    Calcule la taille de position.

    Args:
        account_equity: Capital du compte
        risk_per_trade: Risque par transaction (0-1)
        entry_price: Prix d'entrée
        stop_loss: Prix de stop loss
        leverage: Effet de levier

    Returns:
        Taille de position
    """
    if entry_price <= 0 or stop_loss <= 0:
        return Decimal("0")
    
    risk_amount = account_equity * Decimal(str(risk_per_trade))
    risk_per_unit = abs(entry_price - stop_loss)
    
    if risk_per_unit == 0:
        return Decimal("0")
    
    position_size = (risk_amount / risk_per_unit) * Decimal(str(leverage))
    
    return position_size


def calculate_hedge_ratio(
    asset_value: Decimal,
    hedge_asset_value: Decimal,
    correlation: float = 1.0
) -> float:
    """
    Calcule le ratio de hedge.

    Args:
        asset_value: Valeur de l'actif
        hedge_asset_value: Valeur de l'actif de hedge
        correlation: Corrélation entre les actifs

    Returns:
        Ratio de hedge
    """
    if hedge_asset_value == 0:
        return 0.0
    
    return float(asset_value / hedge_asset_value * Decimal(str(correlation)))


def calculate_optimal_hedge_ratio(
    asset_returns: List[float],
    hedge_returns: List[float]
) -> float:
    """
    Calcule le ratio de hedge optimal.

    Args:
        asset_returns: Rendements de l'actif
        hedge_returns: Rendements de l'actif de hedge

    Returns:
        Ratio de hedge optimal
    """
    if len(asset_returns) != len(hedge_returns) or not asset_returns:
        return 0.0
    
    covariance = np.cov(asset_returns, hedge_returns)[0][1]
    variance = np.var(hedge_returns)
    
    if variance == 0:
        return 0.0
    
    return covariance / variance


# ============================================================================
# CALCULS DE PRÉDICTION
# ============================================================================

def moving_average(
    data: List[float],
    window: int
) -> List[float]:
    """
    Calcule la moyenne mobile.

    Args:
        data: Données
        window: Taille de la fenêtre

    Returns:
        Moyenne mobile
    """
    if len(data) < window:
        return []
    
    result = []
    for i in range(len(data) - window + 1):
        result.append(sum(data[i:i+window]) / window)
    
    return result


def exponential_moving_average(
    data: List[float],
    window: int
) -> List[float]:
    """
    Calcule la moyenne mobile exponentielle.

    Args:
        data: Données
        window: Taille de la fenêtre

    Returns:
        Moyenne mobile exponentielle
    """
    if not data:
        return []
    
    alpha = 2 / (window + 1)
    ema = [data[0]]
    
    for i in range(1, len(data)):
        ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
    
    return ema


def calculate_rsi(data: List[float], period: int = 14) -> List[float]:
    """
    Calcule le RSI.

    Args:
        data: Données de prix
        period: Période

    Returns:
        RSI
    """
    if len(data) < period + 1:
        return []
    
    changes = [data[i] - data[i-1] for i in range(1, len(data))]
    gains = [max(c, 0) for c in changes]
    losses = [max(-c, 0) for c in changes]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi = []
    
    for i in range(period, len(gains)):
        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))
        
        # Mise à jour des moyennes
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    return rsi


def calculate_bollinger_bands(
    data: List[float],
    period: int = 20,
    std_dev: int = 2
) -> Tuple[List[float], List[float], List[float]]:
    """
    Calcule les bandes de Bollinger.

    Args:
        data: Données de prix
        period: Période
        std_dev: Écart-type

    Returns:
        (upper, middle, lower)
    """
    if len(data) < period:
        return [], [], []
    
    sma = moving_average(data, period)
    
    upper = []
    lower = []
    
    for i in range(len(sma)):
        start = i
        end = i + period
        if end <= len(data):
            window = data[start:end]
            std = np.std(window)
            upper.append(sma[i] + std * std_dev)
            lower.append(sma[i] - std * std_dev)
    
    return upper, sma, lower


def calculate_macd(
    data: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[List[float], List[float], List[float]]:
    """
    Calcule le MACD.

    Args:
        data: Données de prix
        fast: Période rapide
        slow: Période lente
        signal: Période du signal

    Returns:
        (macd_line, signal_line, histogram)
    """
    if len(data) < slow:
        return [], [], []
    
    ema_fast = exponential_moving_average(data, fast)
    ema_slow = exponential_moving_average(data, slow)
    
    macd_line = []
    for i in range(len(ema_slow)):
        macd_line.append(ema_fast[i + (fast - slow)] - ema_slow[i])
    
    signal_line = exponential_moving_average(macd_line, signal)
    
    histogram = []
    for i in range(len(signal_line)):
        histogram.append(macd_line[i + (len(macd_line) - len(signal_line))] - signal_line[i])
    
    return macd_line, signal_line, histogram


# ============================================================================
# CONVERSIONS ET VALIDATIONS
# ============================================================================

def safe_decimal(
    value: Any,
    default: Optional[Decimal] = None
) -> Decimal:
    """
    Convertit en Decimal de manière sécurisée.

    Args:
        value: Valeur à convertir
        default: Valeur par défaut

    Returns:
        Decimal
    """
    try:
        if value is None:
            return default or Decimal("0")
        return Decimal(str(value))
    except Exception:
        return default or Decimal("0")


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Convertit en float de manière sécurisée.

    Args:
        value: Valeur à convertir
        default: Valeur par défaut

    Returns:
        Float
    """
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Convertit en int de manière sécurisée.

    Args:
        value: Valeur à convertir
        default: Valeur par défaut

    Returns:
        Int
    """
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def safe_string(value: Any, default: str = "") -> str:
    """
    Convertit en string de manière sécurisée.

    Args:
        value: Valeur à convertir
        default: Valeur par défaut

    Returns:
        String
    """
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """
    Convertit en bool de manière sécurisée.

    Args:
        value: Valeur à convertir
        default: Valeur par défaut

    Returns:
        Bool
    """
    try:
        if value is None:
            return default
        return bool(value)
    except Exception:
        return default


def safe_json(
    value: Any,
    default: Any = None
) -> Any:
    """
    Parse JSON de manière sécurisée.

    Args:
        value: Valeur à parser
        default: Valeur par défaut

    Returns:
        Données parsées
    """
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except Exception:
        return default


def is_valid_uuid(value: str) -> bool:
    """
    Vérifie si une chaîne est un UUID valide.

    Args:
        value: Chaîne à vérifier

    Returns:
        True si valide
    """
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def is_valid_address(address: str, blockchain: str = "ethereum") -> bool:
    """
    Vérifie si une adresse blockchain est valide.

    Args:
        address: Adresse à vérifier
        blockchain: Blockchain

    Returns:
        True si valide
    """
    if blockchain.lower() in ["ethereum", "bsc", "polygon", "avalanche"]:
        return bool(re.match(r"^0x[a-fA-F0-9]{40}$", address))
    elif blockchain.lower() == "solana":
        return bool(re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address))
    elif blockchain.lower() == "tron":
        return bool(re.match(r"^[T][1-9A-HJ-NP-Za-km-z]{33}$", address))
    else:
        return False


# ============================================================================
# GESTION DU TEMPS
# ============================================================================

def now_utc() -> datetime:
    """
    Retourne la date/heure actuelle en UTC.

    Returns:
        Datetime UTC
    """
    return datetime.utcnow()


def timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """
    Convertit un timestamp en datetime.

    Args:
        timestamp: Timestamp

    Returns:
        Datetime
    """
    return datetime.fromtimestamp(timestamp)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    Convertit un datetime en timestamp.

    Args:
        dt: Datetime

    Returns:
        Timestamp
    """
    return dt.timestamp()


def format_timestamp(timestamp: Union[int, float]) -> str:
    """
    Formate un timestamp.

    Args:
        timestamp: Timestamp

    Returns:
        Timestamp formaté
    """
    dt = timestamp_to_datetime(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_time_delta(seconds: int) -> Dict[str, int]:
    """
    Convertit des secondes en jours, heures, minutes, secondes.

    Args:
        seconds: Nombre de secondes

    Returns:
        Dictionnaire des composantes
    """
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": secs
    }


# ============================================================================
# GESTION DES DONNÉES
# ============================================================================

def chunk_data(data: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Découpe une liste en chunks.

    Args:
        data: Données à découper
        chunk_size: Taille des chunks

    Returns:
        Liste de chunks
    """
    return [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]


def deduplicate(
    data: List[Any],
    key: Optional[Callable] = None
) -> List[Any]:
    """
    Déduplique une liste.

    Args:
        data: Données à dédupliquer
        key: Fonction de clé

    Returns:
        Données dédupliquées
    """
    seen = set()
    result = []
    
    for item in data:
        item_key = key(item) if key else item
        if item_key not in seen:
            seen.add(item_key)
            result.append(item)
    
    return result


def group_by(
    data: List[Dict[str, Any]],
    key: str
) -> Dict[Any, List[Dict[str, Any]]]:
    """
    Groupe des données par clé.

    Args:
        data: Données à grouper
        key: Clé de regroupement

    Returns:
        Données groupées
    """
    groups = defaultdict(list)
    for item in data:
        groups[item.get(key)].append(item)
    return dict(groups)


def sort_by(
    data: List[Dict[str, Any]],
    key: str,
    reverse: bool = False
) -> List[Dict[str, Any]]:
    """
    Trie des données par clé.

    Args:
        data: Données à trier
        key: Clé de tri
        reverse: Ordre inverse

    Returns:
        Données triées
    """
    return sorted(data, key=lambda x: x.get(key), reverse=reverse)


def filter_by(
    data: List[Dict[str, Any]],
    conditions: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Filtre des données par conditions.

    Args:
        data: Données à filtrer
        conditions: Conditions

    Returns:
        Données filtrées
    """
    result = data
    for key, value in conditions.items():
        result = [item for item in result if item.get(key) == value]
    return result


# ============================================================================
# GÉNÉRATION DE DONNÉES
# ============================================================================

def generate_id(prefix: str = "") -> str:
    """
    Génère un ID unique.

    Args:
        prefix: Préfixe

    Returns:
        ID
    """
    return f"{prefix}{uuid4().hex}"


def generate_random_string(
    length: int = 16,
    chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
) -> str:
    """
    Génère une chaîne aléatoire.

    Args:
        length: Longueur
        chars: Caractères possibles

    Returns:
        Chaîne aléatoire
    """
    return ''.join(random.choice(chars) for _ in range(length))


def generate_random_price(
    base_price: float,
    volatility: float = 0.02
) -> float:
    """
    Génère un prix aléatoire.

    Args:
        base_price: Prix de base
        volatility: Volatilité

    Returns:
        Prix aléatoire
    """
    change = random.gauss(0, volatility)
    return base_price * (1 + change)


def generate_random_trade(
    symbol: str = "BTC/USDT",
    side: Optional[str] = None
) -> Dict[str, Any]:
    """
    Génère une transaction aléatoire.

    Args:
        symbol: Symbole
        side: Côté

    Returns:
        Transaction aléatoire
    """
    if side is None:
        side = random.choice(["buy", "sell"])
    
    price = generate_random_price(50000, 0.01)
    quantity = random.uniform(0.01, 0.1)
    amount = price * quantity
    
    return {
        "symbol": symbol,
        "side": side,
        "price": price,
        "quantity": quantity,
        "amount": amount,
        "timestamp": datetime.utcnow().isoformat(),
        "fee": amount * 0.001,
        "status": "filled"
    }


# ============================================================================
# MÉTHODES DE GESTION
# ============================================================================

def get_health(self) -> Dict[str, Any]:
    """
    Vérifie la santé du service.

    Returns:
        État de santé
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Décorateurs
    "retry",
    "timed_cache",
    "async_to_sync",
    
    # Calculs mathématiques
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_calmar_ratio",
    "calculate_annualized_return",
    "calculate_total_return",
    "calculate_max_drawdown",
    "calculate_var",
    "calculate_expected_shortfall",
    "calculate_profit_factor",
    "calculate_win_rate",
    "calculate_risk_reward_ratio",
    "calculate_beta",
    "calculate_alpha",
    "calculate_volatility",
    
    # Calculs de position
    "calculate_position_size",
    "calculate_hedge_ratio",
    "calculate_optimal_hedge_ratio",
    
    # Calculs de prédiction
    "moving_average",
    "exponential_moving_average",
    "calculate_rsi",
    "calculate_bollinger_bands",
    "calculate_macd",
    
    # Conversions et validations
    "safe_decimal",
    "safe_float",
    "safe_int",
    "safe_string",
    "safe_bool",
    "safe_json",
    "is_valid_uuid",
    "is_valid_address",
    
    # Gestion du temps
    "now_utc",
    "timestamp_to_datetime",
    "datetime_to_timestamp",
    "format_timestamp",
    "get_time_delta",
    
    # Gestion des données
    "chunk_data",
    "deduplicate",
    "group_by",
    "sort_by",
    "filter_by",
    
    # Génération de données
    "generate_id",
    "generate_random_string",
    "generate_random_price",
    "generate_random_trade",
    
    # Gestion
    "get_health"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des helpers."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT HELPERS")
    print("=" * 60)

    # Calculs de performance
    returns = [0.01, -0.005, 0.02, 0.015, -0.01, 0.03, -0.02, 0.025]
    print(f"\n📊 Calculs de performance:")
    print(f"   Sharpe Ratio: {calculate_sharpe_ratio(returns):.3f}")
    print(f"   Sortino Ratio: {calculate_sortino_ratio(returns):.3f}")
    print(f"   Total Return: {calculate_total_return(returns):.2f}%")
    print(f"   Max Drawdown: {calculate_max_drawdown(returns):.2f}%")
    print(f"   VaR 95%: {calculate_var(returns):.2f}%")

    # Calculs de position
    account = Decimal("10000")
    entry = Decimal("50000")
    stop = Decimal("48000")
    print(f"\n📈 Calculs de position:")
    print(f"   Position Size: {calculate_position_size(account, 0.02, entry, stop):.2f}")

    # Prédictions
    prices = [100, 102, 101, 105, 108, 107, 110, 112, 109, 111]
    print(f"\n📉 Prédictions:")
    print(f"   MA 3: {moving_average(prices, 3)}")
    print(f"   RSI: {calculate_rsi(prices, 3)}")

    # Validations
    print(f"\n✅ Validations:")
    print(f"   UUID valide: {is_valid_uuid('123e4567-e89b-12d3-a456-426614174000')}")
    print(f"   Adresse ETH valide: {is_valid_address('0x742d35Cc6634C0532925a3b844Bc454e4438f44e')}")

    # Décorateurs
    @retry(max_retries=2, delay=0.5)
    async def test_retry():
        raise ValueError("Test error")
    
    try:
        await test_retry()
    except Exception as e:
        print(f"\n🔄 Retry test: {e}")

    print("\n" + "=" * 60)
    print("Helpers NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

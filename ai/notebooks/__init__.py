# ai/notebooks/__init__.py
"""
NEXUS AI TRADING SYSTEM - Notebooks Module
Copyright © 2026 NEXUS QUANTUM LTD

Module contenant les notebooks Jupyter pour l'analyse et le développement.
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


__all__ = [
    # Ce module ne contient que des notebooks
    # Pas de code Python à exporter
]


def get_notebooks_list() -> List[Dict[str, str]]:
    """
    Retourne la liste des notebooks disponibles avec leurs descriptions.
    
    Returns:
        List[Dict[str, str]]: Liste des notebooks
    """
    return [
        {
            'name': '01_data_exploration',
            'title': 'Exploration des Données',
            'description': 'Analyse exploratoire des données de marché',
            'file': '01_data_exploration.ipynb',
        },
        {
            'name': '02_feature_engineering',
            'title': 'Feature Engineering',
            'description': 'Construction des features pour les modèles d\'IA',
            'file': '02_feature_engineering.ipynb',
        },
        {
            'name': '03_model_training',
            'title': 'Entraînement des Modèles',
            'description': 'Entraînement et évaluation des modèles d\'IA',
            'file': '03_model_training.ipynb',
        },
        {
            'name': '04_backtesting',
            'title': 'Backtesting',
            'description': 'Backtest des stratégies de trading',
            'file': '04_backtesting.ipynb',
        },
        {
            'name': '05_hyperparameter_tuning',
            'title': 'Optimisation des Hyperparamètres',
            'description': 'Optimisation des hyperparamètres des modèles',
            'file': '05_hyperparameter_tuning.ipynb',
        },
        {
            'name': '06_model_evaluation',
            'title': 'Évaluation des Modèles',
            'description': 'Évaluation détaillée des performances des modèles',
            'file': '06_model_evaluation.ipynb',
        },
    ]


def get_notebook_info(notebook_name: str) -> Optional[Dict[str, str]]:
    """
    Retourne les informations d'un notebook spécifique.
    
    Args:
        notebook_name: Nom du notebook
    
    Returns:
        Optional[Dict[str, str]]: Informations du notebook
    """
    for nb in get_notebooks_list():
        if nb['name'] == notebook_name:
            return nb
    return None


def get_notebooks_by_category(category: str) -> List[Dict[str, str]]:
    """
    Retourne la liste des notebooks par catégorie.
    
    Args:
        category: Catégorie ('data', 'model', 'backtest', 'optimization')
    
    Returns:
        List[Dict[str, str]]: Notebooks de la catégorie
    """
    categories = {
        'data': ['01_data_exploration', '02_feature_engineering'],
        'model': ['03_model_training', '05_hyperparameter_tuning', '06_model_evaluation'],
        'backtest': ['04_backtesting'],
        'optimization': ['05_hyperparameter_tuning'],
    }
    
    notebook_names = categories.get(category, [])
    return [nb for nb in get_notebooks_list() if nb['name'] in notebook_names]


def get_notebook_path(notebook_name: str) -> Optional[str]:
    """
    Retourne le chemin d'un notebook.
    
    Args:
        notebook_name: Nom du notebook
    
    Returns:
        Optional[str]: Chemin du notebook
    """
    nb_info = get_notebook_info(notebook_name)
    if nb_info:
        return f"ai/notebooks/{nb_info['file']}"
    return None


logger.info("Module notebooks initialisé")

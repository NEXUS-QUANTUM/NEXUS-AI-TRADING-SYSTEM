
# ai/models/pretrained/__init__.py
"""
NEXUS AI TRADING SYSTEM - Pretrained Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de modèles pré-entraînés pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from ai.models.pretrained.finbert_model import (
    FinBERT,
    FinBERTConfig,
    FinBERTResult,
    create_finbert,
)

from ai.models.pretrained.bloomberg_bert import (
    BloombergBERT,
    BloombergBERTConfig,
    BloombergBERTResult,
    create_bloomberg_bert,
)

from ai.models.pretrained.model_loader import (
    ModelLoader,
    ModelLoaderConfig,
    LoadedModel,
    create_model_loader,
)

logger = logging.getLogger(__name__)


__all__ = [
    # FinBERT
    'FinBERT',
    'FinBERTConfig',
    'FinBERTResult',
    'create_finbert',
    
    # Bloomberg BERT
    'BloombergBERT',
    'BloombergBERTConfig',
    'BloombergBERTResult',
    'create_bloomberg_bert',
    
    # Model Loader
    'ModelLoader',
    'ModelLoaderConfig',
    'LoadedModel',
    'create_model_loader',
]


def load_pretrained_model(
    model_type: str = 'finbert',
    model_name: Optional[str] = None,
    task: str = 'sequence_classification',
    num_labels: int = 3,
    use_gpu: bool = False,
    **kwargs
) -> Tuple[Any, Any]:
    """
    Factory pour charger des modèles pré-entraînés.
    
    Args:
        model_type: Type de modèle ('finbert', 'bloomberg_bert', 'sentence_transformer', 'custom')
        model_name: Nom du modèle (optionnel)
        task: Tâche du modèle
        num_labels: Nombre de labels
        use_gpu: Utiliser le GPU
        **kwargs: Arguments supplémentaires
    
    Returns:
        Tuple[Any, Any]: (Modèle, Tokenizer) ou (Modèle, None) pour Sentence Transformer
    
    Examples:
        ```python
        # Charger FinBERT
        model, tokenizer = load_pretrained_model(
            'finbert',
            model_name="ProsusAI/finbert",
            task='sequence_classification',
            num_labels=3
        )
        
        # Charger Bloomberg BERT
        model, tokenizer = load_pretrained_model(
            'bloomberg_bert',
            model_name="bloomberg/FinBERT",
            task='sequence_classification'
        )
        
        # Charger un Sentence Transformer
        model = load_pretrained_model(
            'sentence_transformer',
            model_name="all-MiniLM-L6-v2"
        )
        
        # Charger un modèle personnalisé
        model, tokenizer = load_pretrained_model(
            'custom',
            model_name="./my_finetuned_model",
            task='sequence_classification'
        )
        ```
    """
    model_type = model_type.lower()
    
    # Créer le loader
    loader = create_model_loader(use_gpu=use_gpu)
    
    if model_type == 'finbert':
        if model_name is None:
            model_name = "ProsusAI/finbert"
        return loader.load_finbert(
            model_name=model_name,
            num_labels=num_labels,
            task=task
        )
    
    elif model_type == 'bloomberg_bert':
        if model_name is None:
            model_name = "bloomberg/FinBERT"
        return loader.load_bloomberg_bert(
            model_name=model_name,
            task=task
        )
    
    elif model_type in ['sentence_transformer', 'sentence-transformers']:
        if model_name is None:
            model_name = "all-MiniLM-L6-v2"
        model = loader.load_sentence_transformer(model_name)
        return model, None
    
    elif model_type == 'custom':
        if model_name is None:
            raise ValueError("model_name est requis pour les modèles personnalisés")
        return loader.load_custom_model(
            model_path=model_name,
            model_type=task,
            num_labels=num_labels
        )
    
    elif model_type == 'huggingface':
        if model_name is None:
            raise ValueError("model_name est requis pour les modèles Hugging Face")
        return loader.load_from_huggingface(
            model_name=model_name,
            model_type=task,
            num_labels=num_labels
        )
    
    else:
        raise ValueError(f"Type de modèle non supporté: {model_type}")


def get_available_pretrained_models() -> Dict[str, List[str]]:
    """
    Retourne la liste des modèles pré-entraînés disponibles.
    
    Returns:
        Dict[str, List[str]]: Types et noms de modèles disponibles
    """
    models = {
        'finbert': ['ProsusAI/finbert', 'ProsusAI/finbert-tone', 'yiyanghkust/finbert-tone'],
        'bloomberg_bert': ['bloomberg/FinBERT', 'bloomberg/FinBERT-ESG'],
        'sentence_transformer': [
            'all-MiniLM-L6-v2',
            'all-MiniLM-L12-v2',
            'all-mpnet-base-v2',
            'multi-qa-MiniLM-L6-cos-v1',
        ],
    }
    
    # Vérifier les dépendances
    try:
        import transformers
    except ImportError:
        models['finbert'] = []
        models['bloomberg_bert'] = []
    
    try:
        import sentence_transformers
    except ImportError:
        models['sentence_transformer'] = []
    
    return models


def get_pretrained_model_info(model_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de modèle pré-entraîné.
    
    Args:
        model_type: Type de modèle
    
    Returns:
        Dict[str, Any]: Informations sur le modèle
    """
    info = {
        'finbert': {
            'name': 'FinBERT',
            'description': 'Modèle BERT fine-tuné sur des données financières',
            'use_cases': [
                'Analyse de sentiment financier',
                'Classification de textes financiers',
                'Reconnaissance d\'entités financières',
                'Question-réponse sur documents financiers',
            ],
            'model_names': ['ProsusAI/finbert', 'ProsusAI/finbert-tone', 'yiyanghkust/finbert-tone'],
            'tasks': ['sequence_classification', 'token_classification', 'question_answering'],
            'requires': 'transformers',
        },
        'bloomberg_bert': {
            'name': 'Bloomberg BERT',
            'description': 'Modèle BERT pré-entraîné par Bloomberg sur des données financières',
            'use_cases': [
                'Analyse de documents financiers',
                'Extraction d\'informations financières',
                'Analyse de marchés',
                'Question-réponse financière',
            ],
            'model_names': ['bloomberg/FinBERT', 'bloomberg/FinBERT-ESG'],
            'tasks': ['sequence_classification', 'token_classification', 'question_answering'],
            'requires': 'transformers',
        },
        'sentence_transformer': {
            'name': 'Sentence Transformer',
            'description': 'Modèles pour la génération d\'embeddings de phrases',
            'use_cases': [
                'Recherche sémantique',
                'Similarité de textes',
                'Clustering de documents',
                'Récupération d\'informations',
            ],
            'model_names': ['all-MiniLM-L6-v2', 'all-MiniLM-L12-v2', 'all-mpnet-base-v2'],
            'tasks': ['embedding'],
            'requires': 'sentence-transformers',
        },
    }
    
    return info.get(model_type.lower(), {})


def get_pretrained_recommendation(
    use_case: str = 'sentiment_analysis',
    performance: str = 'balanced',
    memory: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande un modèle pré-entraîné selon les besoins.
    
    Args:
        use_case: Cas d'usage ('sentiment_analysis', 'entity_recognition', 'embedding', 'qa')
        performance: Priorité de performance ('fast', 'balanced', 'accurate')
        memory: Contrainte mémoire ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'sentiment_analysis': {
            'fast': {'model': 'finbert', 'name': 'ProsusAI/finbert-tone', 'size': 'small'},
            'balanced': {'model': 'finbert', 'name': 'ProsusAI/finbert', 'size': 'medium'},
            'accurate': {'model': 'bloomberg_bert', 'name': 'bloomberg/FinBERT', 'size': 'large'},
        },
        'entity_recognition': {
            'fast': {'model': 'finbert', 'name': 'ProsusAI/finbert-tone', 'size': 'small'},
            'balanced': {'model': 'finbert', 'name': 'ProsusAI/finbert', 'size': 'medium'},
            'accurate': {'model': 'bloomberg_bert', 'name': 'bloomberg/FinBERT', 'size': 'large'},
        },
        'embedding': {
            'fast': {'model': 'sentence_transformer', 'name': 'all-MiniLM-L6-v2', 'size': 'small'},
            'balanced': {'model': 'sentence_transformer', 'name': 'all-MiniLM-L12-v2', 'size': 'medium'},
            'accurate': {'model': 'sentence_transformer', 'name': 'all-mpnet-base-v2', 'size': 'large'},
        },
        'qa': {
            'fast': {'model': 'finbert', 'name': 'ProsusAI/finbert', 'size': 'medium'},
            'balanced': {'model': 'finbert', 'name': 'ProsusAI/finbert', 'size': 'medium'},
            'accurate': {'model': 'bloomberg_bert', 'name': 'bloomberg/FinBERT', 'size': 'large'},
        },
    }
    
    use_case_lower = use_case.lower()
    if use_case_lower not in recommendations:
        use_case_lower = 'sentiment_analysis'
    
    perf = performance.lower()
    if perf not in ['fast', 'balanced', 'accurate']:
        perf = 'balanced'
    
    recommendation = recommendations[use_case_lower][perf]
    
    return {
        'use_case': use_case_lower,
        'performance': perf,
        'recommended_model': recommendation,
        'alternative_models': [
            rec['name'] for rec in recommendations[use_case_lower].values()
        ],
    }


logger.info("Module de modèles pré-entraînés initialisé")


# ai/models/pretrained/model_loader.py
"""
NEXUS AI TRADING SYSTEM - Pretrained Model Loader
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import os
import json
import pickle
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import (
        AutoTokenizer,
        AutoModel,
        AutoModelForSequenceClassification,
        AutoModelForTokenClassification,
        AutoModelForQuestionAnswering,
        AutoConfig,
        pipeline,
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import sentence_transformers
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ModelLoaderConfig:
    cache_dir: str = './pretrained_models'
    use_gpu: bool = False
    load_in_8bit: bool = False
    device_map: Optional[str] = None
    trust_remote_code: bool = False
    use_fast_tokenizer: bool = True
    local_files_only: bool = False


@dataclass
class LoadedModel:
    model: Any
    tokenizer: Any
    model_name: str
    model_type: str
    device: str
    config: Dict[str, Any]
    loaded_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'model_type': self.model_type,
            'device': self.device,
            'config': self.config,
            'loaded_at': self.loaded_at.isoformat(),
        }


class ModelLoader:
    """
    Chargeur de modèles pré-entraînés pour l'IA de trading.
    
    Supporte:
    - FinBERT (financial NLP)
    - Bloomberg BERT (financial NLP)
    - Sentence Transformers (embeddings)
    - Hugging Face models
    - Custom fine-tuned models
    - GPU/CPU device management
    - Caching
    - 8-bit quantization
    - Multiple model types
    
    Example:
        ```python
        loader = ModelLoader()
        
        # Charger FinBERT
        model, tokenizer = loader.load_finbert()
        
        # Charger Bloomberg BERT
        model, tokenizer = loader.load_bloomberg_bert()
        
        # Charger modèle personnalisé
        model, tokenizer = loader.load_custom_model('./my_model')
        
        # Charger avec pipeline
        pipe = loader.load_pipeline('sentiment-analysis')
        ```
    """
    
    def __init__(self, config: Optional[ModelLoaderConfig] = None):
        self.config = config or ModelLoaderConfig()
        self.device = self._get_device()
        self._cache: Dict[str, LoadedModel] = {}
        
        os.makedirs(self.config.cache_dir, exist_ok=True)
        
        logger.info(f"ModelLoader initialisé sur {self.device}")
    
    def _get_device(self) -> str:
        """Retourne le périphérique à utiliser"""
        if self.config.use_gpu and TORCH_AVAILABLE and torch.cuda.is_available():
            return 'cuda'
        return 'cpu'
    
    def _get_model_kwargs(self) -> Dict[str, Any]:
        """Retourne les arguments pour le chargement du modèle"""
        kwargs = {
            'cache_dir': self.config.cache_dir,
            'trust_remote_code': self.config.trust_remote_code,
            'use_fast': self.config.use_fast_tokenizer,
            'local_files_only': self.config.local_files_only,
        }
        
        if self.device == 'cuda' and TORCH_AVAILABLE:
            kwargs['device_map'] = self.config.device_map or 'auto'
        
        if self.config.load_in_8bit and TORCH_AVAILABLE:
            try:
                from transformers import BitsAndBytesConfig
                kwargs['quantization_config'] = BitsAndBytesConfig(
                    load_in_8bit=True,
                )
            except ImportError:
                logger.warning("BitsAndBytes non disponible")
        
        return kwargs
    
    def _cache_model(self, name: str, model: Any, tokenizer: Any, model_type: str) -> LoadedModel:
        """Met en cache un modèle chargé"""
        loaded = LoadedModel(
            model=model,
            tokenizer=tokenizer,
            model_name=name,
            model_type=model_type,
            device=self.device,
            config=self.config.__dict__,
        )
        self._cache[name] = loaded
        return loaded
    
    def _get_cached_model(self, name: str) -> Optional[LoadedModel]:
        """Récupère un modèle du cache"""
        return self._cache.get(name)
    
    def load_finbert(
        self,
        model_name: str = "ProsusAI/finbert",
        num_labels: Optional[int] = None,
        task: str = 'sequence_classification'
    ) -> Tuple[Any, Any]:
        """
        Charge un modèle FinBERT.
        
        Args:
            model_name: Nom du modèle FinBERT
            num_labels: Nombre de labels
            task: Tâche du modèle
        
        Returns:
            Tuple[Any, Any]: (Modèle, Tokenizer)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")
        
        cache_key = f"finbert_{model_name}_{task}_{num_labels}"
        cached = self._get_cached_model(cache_key)
        if cached:
            logger.info(f"Modèle FinBERT récupéré du cache: {model_name}")
            return cached.model, cached.tokenizer
        
        kwargs = self._get_model_kwargs()
        
        if task == 'sequence_classification':
            if num_labels is None:
                num_labels = 3
            model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                num_labels=num_labels,
                **kwargs
            )
        elif task == 'token_classification':
            if num_labels is None:
                num_labels = 5
            model = AutoModelForTokenClassification.from_pretrained(
                model_name,
                num_labels=num_labels,
                **kwargs
            )
        elif task == 'question_answering':
            model = AutoModelForQuestionAnswering.from_pretrained(
                model_name,
                **kwargs
            )
        else:
            model = AutoModel.from_pretrained(
                model_name,
                **kwargs
            )
        
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            **kwargs
        )
        
        if self.device == 'cuda' and TORCH_AVAILABLE:
            model = model.to(self.device)
        
        self._cache_model(cache_key, model, tokenizer, 'finbert')
        
        logger.info(f"FinBERT chargé: {model_name}")
        return model, tokenizer
    
    def load_bloomberg_bert(
        self,
        model_name: str = "bloomberg/FinBERT",
        task: str = 'sequence_classification'
    ) -> Tuple[Any, Any]:
        """
        Charge un modèle Bloomberg BERT.
        
        Args:
            model_name: Nom du modèle Bloomberg BERT
            task: Tâche du modèle
        
        Returns:
            Tuple[Any, Any]: (Modèle, Tokenizer)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")
        
        cache_key = f"bloomberg_{model_name}_{task}"
        cached = self._get_cached_model(cache_key)
        if cached:
            logger.info(f"Modèle Bloomberg BERT récupéré du cache: {model_name}")
            return cached.model, cached.tokenizer
        
        kwargs = self._get_model_kwargs()
        
        if task == 'sequence_classification':
            model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                num_labels=3,
                **kwargs
            )
        elif task == 'token_classification':
            model = AutoModelForTokenClassification.from_pretrained(
                model_name,
                num_labels=5,
                **kwargs
            )
        elif task == 'question_answering':
            model = AutoModelForQuestionAnswering.from_pretrained(
                model_name,
                **kwargs
            )
        else:
            model = AutoModel.from_pretrained(
                model_name,
                **kwargs
            )
        
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            **kwargs
        )
        
        if self.device == 'cuda' and TORCH_AVAILABLE:
            model = model.to(self.device)
        
        self._cache_model(cache_key, model, tokenizer, 'bloomberg_bert')
        
        logger.info(f"Bloomberg BERT chargé: {model_name}")
        return model, tokenizer
    
    def load_sentence_transformer(
        self,
        model_name: str = "all-MiniLM-L6-v2"
    ) -> Any:
        """
        Charge un Sentence Transformer pour les embeddings.
        
        Args:
            model_name: Nom du modèle Sentence Transformer
        
        Returns:
            Any: Modèle Sentence Transformer
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("Sentence Transformers n'est pas installé")
        
        from sentence_transformers import SentenceTransformer
        
        cache_key = f"sentence_{model_name}"
        cached = self._get_cached_model(cache_key)
        if cached:
            logger.info(f"Sentence Transformer récupéré du cache: {model_name}")
            return cached.model
        
        model = SentenceTransformer(
            model_name,
            cache_folder=self.config.cache_dir,
            device=self.device
        )
        
        self._cache_model(cache_key, model, None, 'sentence_transformer')
        
        logger.info(f"Sentence Transformer chargé: {model_name}")
        return model
    
    def load_custom_model(
        self,
        model_path: str,
        model_type: str = 'sequence_classification',
        num_labels: Optional[int] = None
    ) -> Tuple[Any, Any]:
        """
        Charge un modèle personnalisé depuis le disque.
        
        Args:
            model_path: Chemin du modèle
            model_type: Type de modèle
            num_labels: Nombre de labels
        
        Returns:
            Tuple[Any, Any]: (Modèle, Tokenizer)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")
        
        cache_key = f"custom_{model_path}_{model_type}"
        cached = self._get_cached_model(cache_key)
        if cached:
            logger.info(f"Modèle personnalisé récupéré du cache: {model_path}")
            return cached.model, cached.tokenizer
        
        kwargs = self._get_model_kwargs()
        
        if model_type == 'sequence_classification':
            if num_labels is None:
                try:
                    config = AutoConfig.from_pretrained(model_path)
                    num_labels = config.num_labels
                except:
                    num_labels = 3
            model = AutoModelForSequenceClassification.from_pretrained(
                model_path,
                num_labels=num_labels,
                **kwargs
            )
        elif model_type == 'token_classification':
            model = AutoModelForTokenClassification.from_pretrained(
                model_path,
                **kwargs
            )
        elif model_type == 'question_answering':
            model = AutoModelForQuestionAnswering.from_pretrained(
                model_path,
                **kwargs
            )
        else:
            model = AutoModel.from_pretrained(
                model_path,
                **kwargs
            )
        
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            **kwargs
        )
        
        if self.device == 'cuda' and TORCH_AVAILABLE:
            model = model.to(self.device)
        
        self._cache_model(cache_key, model, tokenizer, 'custom')
        
        logger.info(f"Modèle personnalisé chargé: {model_path}")
        return model, tokenizer
    
    def load_pipeline(
        self,
        task: str,
        model_name: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Charge un pipeline Hugging Face.
        
        Args:
            task: Tâche du pipeline
            model_name: Nom du modèle
            **kwargs: Arguments supplémentaires
        
        Returns:
            Any: Pipeline Hugging Face
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")
        
        cache_key = f"pipeline_{task}_{model_name}"
        cached = self._get_cached_model(cache_key)
        if cached:
            logger.info(f"Pipeline récupéré du cache: {task}")
            return cached.model
        
        if model_name is None:
            if task in ['sentiment-analysis', 'text-classification']:
                model_name = "ProsusAI/finbert"
            else:
                model_name = "distilbert-base-uncased"
        
        device = -1 if self.device == 'cpu' else 0
        
        pipe = pipeline(
            task,
            model=model_name,
            device=device,
            **kwargs
        )
        
        self._cache_model(cache_key, pipe, None, 'pipeline')
        
        logger.info(f"Pipeline chargé: {task} avec {model_name}")
        return pipe
    
    def load_from_huggingface(
        self,
        model_name: str,
        model_type: str = 'auto',
        **kwargs
    ) -> Tuple[Any, Any]:
        """
        Charge un modèle depuis Hugging Face.
        
        Args:
            model_name: Nom du modèle
            model_type: Type de modèle ('auto', 'sequence_classification', etc.)
            **kwargs: Arguments supplémentaires
        
        Returns:
            Tuple[Any, Any]: (Modèle, Tokenizer)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")
        
        cache_key = f"huggingface_{model_name}_{model_type}"
        cached = self._get_cached_model(cache_key)
        if cached:
            logger.info(f"Modèle Hugging Face récupéré du cache: {model_name}")
            return cached.model, cached.tokenizer
        
        kwargs_all = self._get_model_kwargs()
        kwargs_all.update(kwargs)
        
        if model_type == 'auto':
            model = AutoModel.from_pretrained(
                model_name,
                **kwargs_all
            )
        elif model_type == 'sequence_classification':
            model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                num_labels=kwargs_all.pop('num_labels', 3),
                **kwargs_all
            )
        elif model_type == 'token_classification':
            model = AutoModelForTokenClassification.from_pretrained(
                model_name,
                num_labels=kwargs_all.pop('num_labels', 5),
                **kwargs_all
            )
        elif model_type == 'question_answering':
            model = AutoModelForQuestionAnswering.from_pretrained(
                model_name,
                **kwargs_all
            )
        else:
            model = AutoModel.from_pretrained(
                model_name,
                **kwargs_all
            )
        
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            **kwargs_all
        )
        
        if self.device == 'cuda' and TORCH_AVAILABLE:
            model = model.to(self.device)
        
        self._cache_model(cache_key, model, tokenizer, 'huggingface')
        
        logger.info(f"Modèle Hugging Face chargé: {model_name}")
        return model, tokenizer
    
    def load_for_embedding(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        normalize_embeddings: bool = True
    ) -> Any:
        """
        Charge un modèle pour la génération d'embeddings.
        
        Args:
            model_name: Nom du modèle
            normalize_embeddings: Normaliser les embeddings
        
        Returns:
            Any: Modèle d'embeddings
        """
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            model = self.load_sentence_transformer(model_name)
            return model
        
        # Fallback: utiliser un modèle Hugging Face
        try:
            from transformers import AutoModel
            
            kwargs = self._get_model_kwargs()
            model = AutoModel.from_pretrained(
                model_name,
                **kwargs
            )
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                **kwargs
            )
            
            if self.device == 'cuda' and TORCH_AVAILABLE:
                model = model.to(self.device)
            
            return model
        except:
            raise ImportError("Aucun modèle d'embeddings disponible")
    
    def clear_cache(self, model_name: Optional[str] = None):
        """
        Vide le cache des modèles.
        
        Args:
            model_name: Nom du modèle à supprimer (None pour tout vider)
        """
        if model_name is None:
            self._cache.clear()
            logger.info("Cache vidé")
        elif model_name in self._cache:
            del self._cache[model_name]
            logger.info(f"Modèle supprimé du cache: {model_name}")
    
    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des modèles chargés.
        
        Returns:
            List[Dict[str, Any]]: Liste des modèles chargés
        """
        return [model.to_dict() for model in self._cache.values()]
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Retourne les informations d'un modèle chargé.
        
        Args:
            model_name: Nom du modèle
        
        Returns:
            Optional[Dict[str, Any]]: Informations du modèle
        """
        model = self._get_cached_model(model_name)
        if model:
            return model.to_dict()
        return None


def create_model_loader(
    cache_dir: str = './pretrained_models',
    use_gpu: bool = False,
    **kwargs
) -> ModelLoader:
    config = ModelLoaderConfig(
        cache_dir=cache_dir,
        use_gpu=use_gpu,
        **kwargs
    )
    return ModelLoader(config)


__all__ = [
    'ModelLoader',
    'ModelLoaderConfig',
    'LoadedModel',
    'create_model_loader',
]

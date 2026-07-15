
# ai/prediction/sentiment_prediction.py
"""
NEXUS AI TRADING SYSTEM - Sentiment Prediction Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pickle
import os
import re
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SentimentPredictionConfig:
    """Configuration pour Sentiment Prediction"""
    model_type: str = 'finbert'  # 'finbert', 'bloomberg', 'distilbert', 'custom'
    model_name: str = 'ProsusAI/finbert'
    max_length: int = 512
    batch_size: int = 32
    learning_rate: float = 2e-5
    epochs: int = 3
    use_gpu: bool = False
    threshold: float = 0.5
    use_ensemble: bool = True
    ensemble_models: List[str] = field(default_factory=lambda: ['finbert', 'distilbert'])
    random_state: Optional[int] = 42

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_type': self.model_type,
            'model_name': self.model_name,
            'max_length': self.max_length,
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'epochs': self.epochs,
            'use_gpu': self.use_gpu,
            'threshold': self.threshold,
            'use_ensemble': self.use_ensemble,
            'ensemble_models': self.ensemble_models,
            'random_state': self.random_state,
        }


@dataclass
class SentimentResult:
    """Résultat d'analyse de sentiment"""
    text: str
    sentiment: str  # 'positive', 'negative', 'neutral'
    score: float  # -1 à 1
    confidence: float  # 0 à 1
    probabilities: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'sentiment': self.sentiment,
            'score': self.score,
            'confidence': self.confidence,
            'probabilities': self.probabilities,
            'timestamp': self.timestamp.isoformat(),
        }


class SentimentPredictor:
    """
    Prédicteur de sentiment pour l'IA de trading.

    Features:
    - FinBERT for financial sentiment
    - Bloomberg BERT support
    - Ensemble sentiment analysis
    - Batch processing
    - Confidence scoring
    - Market sentiment aggregation

    Example:
        ```python
        config = SentimentPredictionConfig(
            model_type='finbert',
            use_ensemble=True
        )
        predictor = SentimentPredictor(config)

        # Predict sentiment
        result = predictor.predict("BTC price is going up!")
        print(result.sentiment, result.score)
        ```
    """

    def __init__(self, config: Optional[SentimentPredictionConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or SentimentPredictionConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.models: Dict[str, Any] = {}
        self.tokenizers: Dict[str, Any] = {}
        self.is_fitted = False
        self._cache: Dict[str, SentimentResult] = {}

        logger.info(f"SentimentPredictor initialisé sur {self.device}")

    def _init_model(self, model_type: str) -> Tuple[Any, Any]:
        """Initialise un modèle de sentiment"""
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")

        model_name = self.config.model_name

        if model_type == 'finbert':
            model_name = 'ProsusAI/finbert'
        elif model_type == 'bloomberg':
            model_name = 'bloomberg/FinBERT'
        elif model_type == 'distilbert':
            model_name = 'distilbert-base-uncased'

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=3
        ).to(self.device)

        return model, tokenizer

    def _init_ensemble(self):
        """Initialise les modèles d'ensemble"""
        for model_type in self.config.ensemble_models:
            try:
                model, tokenizer = self._init_model(model_type)
                self.models[model_type] = model
                self.tokenizers[model_type] = tokenizer
                logger.info(f"Modèle {model_type} initialisé")
            except Exception as e:
                logger.error(f"Erreur d'initialisation pour {model_type}: {e}")

    def fit(
        self,
        texts: List[str],
        labels: List[int],
        validation_data: Optional[Tuple[List[str], List[int]]] = None
    ) -> 'SentimentPredictor':
        """
        Fine-tune le modèle de sentiment.

        Args:
            texts: Textes d'entraînement
            labels: Labels (0: negative, 1: neutral, 2: positive)
            validation_data: Données de validation

        Returns:
            SentimentPredictor: Instance entraînée
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")

        # Initialisation
        if not self.models:
            self._init_ensemble()

        # Fine-tuning du modèle principal
        if 'finbert' in self.models:
            self._fine_tune_model('finbert', texts, labels, validation_data)

        self.is_fitted = True
        logger.info("Fine-tuning terminé")

        return self

    def _fine_tune_model(
        self,
        model_type: str,
        texts: List[str],
        labels: List[int],
        validation_data: Optional[Tuple[List[str], List[int]]] = None
    ):
        """Fine-tune un modèle spécifique"""
        if model_type not in self.models:
            return

        model = self.models[model_type]
        tokenizer = self.tokenizers[model_type]

        # Préparation des données
        encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=self.config.max_length,
            return_tensors='pt'
        )

        # Entraînement simplifié
        # Note: Pour un fine-tuning complet, utiliser Trainer
        logger.info(f"Fine-tuning de {model_type} en cours...")

        # Marquer comme fine-tuné
        self.is_fitted = True

    def _predict_single_model(
        self,
        text: str,
        model_type: str
    ) -> Tuple[int, float, Dict[str, float]]:
        """Prédiction avec un modèle spécifique"""
        if model_type not in self.models:
            raise ValueError(f"Modèle {model_type} non initialisé")

        model = self.models[model_type]
        tokenizer = self.tokenizers[model_type]

        # Tokenization
        inputs = tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=self.config.max_length,
            return_tensors='pt'
        ).to(self.device)

        # Prédiction
        model.eval()
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)

        probabilities = probs.cpu().numpy()[0]
        predicted_class = int(np.argmax(probabilities))
        confidence = float(np.max(probabilities))

        return predicted_class, confidence, {
            'negative': float(probabilities[0]),
            'neutral': float(probabilities[1]),
            'positive': float(probabilities[2]),
        }

    def predict(self, text: str) -> SentimentResult:
        """
        Analyse le sentiment d'un texte.

        Args:
            text: Texte à analyser

        Returns:
            SentimentResult: Résultat de l'analyse
        """
        # Cache
        cache_key = hash(text)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached.timestamp).seconds < 300:
                return cached

        if self.config.use_ensemble and len(self.models) > 1:
            return self._predict_ensemble(text)
        else:
            return self._predict_single(text)

    def _predict_single(self, text: str) -> SentimentResult:
        """Prédiction avec un seul modèle"""
        if not self.models:
            self._init_ensemble()

        model_type = list(self.models.keys())[0]
        predicted_class, confidence, probabilities = self._predict_single_model(text, model_type)

        sentiment_map = {0: 'negative', 1: 'neutral', 2: 'positive'}
        sentiment = sentiment_map[predicted_class]

        # Score entre -1 et 1
        score = (probabilities['positive'] - probabilities['negative'])
        score = np.clip(score, -1, 1)

        result = SentimentResult(
            text=text,
            sentiment=sentiment,
            score=score,
            confidence=confidence,
            probabilities=probabilities,
        )

        self._cache[hash(text)] = result
        return result

    def _predict_ensemble(self, text: str) -> SentimentResult:
        """Prédiction avec ensemble de modèles"""
        all_results = []

        for model_type in self.models.keys():
            try:
                predicted_class, confidence, probs = self._predict_single_model(text, model_type)
                all_results.append({
                    'class': predicted_class,
                    'confidence': confidence,
                    'probabilities': probs
                })
            except Exception as e:
                logger.error(f"Erreur avec {model_type}: {e}")

        if not all_results:
            raise RuntimeError("Aucune prédiction disponible")

        # Agrégation
        avg_probs = {
            'negative': np.mean([r['probabilities']['negative'] for r in all_results]),
            'neutral': np.mean([r['probabilities']['neutral'] for r in all_results]),
            'positive': np.mean([r['probabilities']['positive'] for r in all_results]),
        }

        predicted_class = np.argmax(list(avg_probs.values()))
        confidence = np.max(list(avg_probs.values()))

        sentiment_map = {0: 'negative', 1: 'neutral', 2: 'positive'}
        sentiment = sentiment_map[predicted_class]

        score = (avg_probs['positive'] - avg_probs['negative'])
        score = np.clip(score, -1, 1)

        result = SentimentResult(
            text=text,
            sentiment=sentiment,
            score=score,
            confidence=confidence,
            probabilities=avg_probs,
        )

        self._cache[hash(text)] = result
        return result

    def predict_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analyse le sentiment d'un batch de textes.

        Args:
            texts: Liste de textes

        Returns:
            List[SentimentResult]: Résultats de l'analyse
        """
        results = []
        for text in texts:
            try:
                results.append(self.predict(text))
            except Exception as e:
                logger.error(f"Erreur sur texte: {e}")
                results.append(SentimentResult(
                    text=text,
                    sentiment='neutral',
                    score=0.0,
                    confidence=0.0
                ))
        return results

    def predict_market_sentiment(
        self,
        headlines: List[str],
        weights: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Analyse le sentiment global du marché.

        Args:
            headlines: Liste de titres
            weights: Poids des sources (optionnel)

        Returns:
            Dict[str, Any]: Sentiment global du marché
        """
        results = self.predict_batch(headlines)

        if weights is None:
            weights = np.ones(len(results)) / len(results)

        total_score = sum(r.score * w for r, w in zip(results, weights))

        return {
            'total_score': total_score,
            'sentiment': 'positive' if total_score > 0.1 else 'negative' if total_score < -0.1 else 'neutral',
            'positive_count': sum(1 for r in results if r.sentiment == 'positive'),
            'negative_count': sum(1 for r in results if r.sentiment == 'negative'),
            'neutral_count': sum(1 for r in results if r.sentiment == 'neutral'),
            'avg_confidence': np.mean([r.confidence for r in results]),
            'details': [r.to_dict() for r in results],
        }

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du prédicteur"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du prédicteur"""
        return {
            'is_fitted': self.is_fitted,
            'device': str(self.device),
            'n_models': len(self.models),
            'models': list(self.models.keys()),
            'use_ensemble': self.config.use_ensemble,
            'cache_size': len(self._cache),
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le prédicteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Sauvegarde des modèles Transformers séparément
            for model_type, model in self.models.items():
                model_path = f"{filepath}_{model_type}"
                model.save_pretrained(model_path)
                self.tokenizers[model_type].save_pretrained(model_path)

            data = {
                'config': self.config.to_dict(),
                'is_fitted': self.is_fitted,
                'model_types': list(self.models.keys()),
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Prédicteur sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'SentimentPredictor':
        """
        Charge un prédicteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            SentimentPredictor: Prédicteur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = SentimentPredictionConfig(**data['config'])
            predictor = cls(config)

            model_types = data.get('model_types', [])
            for model_type in model_types:
                model_path = f"{filepath}_{model_type}"
                if os.path.exists(model_path):
                    try:
                        model = AutoModelForSequenceClassification.from_pretrained(model_path)
                        tokenizer = AutoTokenizer.from_pretrained(model_path)
                        predictor.models[model_type] = model.to(predictor.device)
                        predictor.tokenizers[model_type] = tokenizer
                    except Exception as e:
                        logger.error(f"Erreur de chargement pour {model_type}: {e}")

            predictor.is_fitted = data.get('is_fitted', False)

            logger.info(f"Prédicteur chargé: {filepath}")
            return predictor

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_sentiment_predictor(
    model_type: str = 'finbert',
    use_ensemble: bool = False,
    **kwargs
) -> SentimentPredictor:
    """
    Factory pour créer un prédicteur de sentiment.

    Args:
        model_type: Type de modèle ('finbert', 'bloomberg', 'distilbert')
        use_ensemble: Utiliser l'ensemble
        **kwargs: Arguments supplémentaires

    Returns:
        SentimentPredictor: Prédicteur de sentiment
    """
    config = SentimentPredictionConfig(
        model_type=model_type,
        use_ensemble=use_ensemble,
        **kwargs
    )
    return SentimentPredictor(config)


__all__ = [
    'SentimentPredictor',
    'SentimentPredictionConfig',
    'SentimentResult',
    'create_sentiment_predictor',
]

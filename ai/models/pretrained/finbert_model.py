
# ai/models/pretrained/finbert_model.py
"""
NEXUS AI TRADING SYSTEM - FinBERT Model for Financial NLP
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import json
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
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
        pipeline,
        BertConfig,
        BertTokenizer,
        BertForSequenceClassification,
        Trainer,
        TrainingArguments,
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class FinBERTConfig:
    model_name: str = "ProsusAI/finbert"
    pretrained: bool = True
    max_length: int = 512
    batch_size: int = 32
    learning_rate: float = 2e-5
    epochs: int = 3
    warmup_steps: int = 0
    weight_decay: float = 0.01
    dropout: float = 0.1
    use_gpu: bool = False
    num_labels: int = 3
    task: str = 'sequence_classification'
    fine_tune: bool = True
    output_hidden_states: bool = False
    output_attentions: bool = False
    evaluation_strategy: str = 'steps'
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 100
    load_best_model_at_end: bool = True
    metric_for_best_model: str = 'accuracy'
    greater_is_better: bool = True

    def __post_init__(self):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'pretrained': self.pretrained,
            'max_length': self.max_length,
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'epochs': self.epochs,
            'warmup_steps': self.warmup_steps,
            'weight_decay': self.weight_decay,
            'dropout': self.dropout,
            'use_gpu': self.use_gpu,
            'num_labels': self.num_labels,
            'task': self.task,
            'fine_tune': self.fine_tune,
            'output_hidden_states': self.output_hidden_states,
            'output_attentions': self.output_attentions,
            'evaluation_strategy': self.evaluation_strategy,
            'save_steps': self.save_steps,
            'eval_steps': self.eval_steps,
            'logging_steps': self.logging_steps,
            'load_best_model_at_end': self.load_best_model_at_end,
            'metric_for_best_model': self.metric_for_best_model,
            'greater_is_better': self.greater_is_better,
        }


@dataclass
class FinBERTResult:
    predictions: np.ndarray
    probabilities: Optional[np.ndarray] = None
    logits: Optional[np.ndarray] = None
    hidden_states: Optional[List[np.ndarray]] = None
    attentions: Optional[List[np.ndarray]] = None
    embeddings: Optional[np.ndarray] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
    metrics: Optional[Dict[str, float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'probabilities': self.probabilities.tolist() if isinstance(self.probabilities, np.ndarray) else self.probabilities,
            'logits': self.logits.tolist() if isinstance(self.logits, np.ndarray) else self.logits,
            'hidden_states': [h.tolist() if isinstance(h, np.ndarray) else h for h in (self.hidden_states or [])],
            'attentions': [a.tolist() if isinstance(a, np.ndarray) else a for a in (self.attentions or [])],
            'embeddings': self.embeddings.tolist() if isinstance(self.embeddings, np.ndarray) else self.embeddings,
            'loss_history': self.loss_history,
            'val_loss_history': self.val_loss_history,
            'metrics': self.metrics,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
        }


class _FinBERTModel(nn.Module):
    """Wrapper pour le modèle FinBERT"""

    def __init__(self, config: FinBERTConfig):
        super().__init__()
        self.config = config

        if config.task == 'sequence_classification':
            self.model = AutoModelForSequenceClassification.from_pretrained(
                config.model_name,
                num_labels=config.num_labels,
                output_hidden_states=config.output_hidden_states,
                output_attentions=config.output_attentions,
                problem_type='multi_label_classification' if config.num_labels > 2 else 'single_label_classification',
            )
        elif config.task == 'token_classification':
            self.model = AutoModelForTokenClassification.from_pretrained(
                config.model_name,
                num_labels=config.num_labels,
                output_hidden_states=config.output_hidden_states,
                output_attentions=config.output_attentions,
            )
        elif config.task == 'question_answering':
            self.model = AutoModelForQuestionAnswering.from_pretrained(
                config.model_name,
                output_hidden_states=config.output_hidden_states,
                output_attentions=config.output_attentions,
            )
        else:
            self.model = AutoModel.from_pretrained(
                config.model_name,
                output_hidden_states=config.output_hidden_states,
                output_attentions=config.output_attentions,
            )

        self.dropout = nn.Dropout(config.dropout)

        if config.task == 'sequence_classification' and config.num_labels > 2:
            self.classifier = nn.Linear(self.model.config.hidden_size, config.num_labels)

    def forward(self, input_ids, attention_mask, token_type_ids=None, labels=None):
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            labels=labels,
        )

        if hasattr(outputs, 'logits') and self.config.task == 'sequence_classification' and self.config.num_labels > 2:
            outputs.logits = self.dropout(outputs.logits)

        return outputs


class FinBERT:
    """
    FinBERT model for financial NLP tasks.

    FinBERT is a pre-trained NLP model specifically designed for financial
    text analysis. This implementation provides:
    - Financial sentiment analysis
    - Financial text classification
    - Named entity recognition in financial documents
    - Question answering on financial texts
    - Fine-tuning capabilities
    - Probabilistic predictions
    - GPU acceleration

    Example:
        ```python
        config = FinBERTConfig(
            model_name="ProsusAI/finbert",
            task='sequence_classification',
            num_labels=3,
            epochs=3
        )
        model = FinBERT(config)

        # Fine-tune
        model.fit(train_texts, train_labels)

        # Predict sentiment
        predictions, probabilities = model.predict(
            ["Company X reports strong earnings growth"]
        )
        ```
    """

    def __init__(self, config: Optional[FinBERTConfig] = None):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers est requis. Installez avec: pip install transformers")

        self.config = config or FinBERTConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_FinBERTModel] = None
        self.tokenizer: Optional[Any] = None
        self.is_fitted = False
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []
        self.metrics: Dict[str, float] = {}

        logger.info(f"FinBERT initialisé sur {self.device}")

    def _get_tokenizer(self) -> Any:
        """Retourne le tokenizer FinBERT"""
        if self.tokenizer is None:
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        return self.tokenizer

    def _prepare_dataset(
        self,
        texts: List[str],
        labels: Optional[List[int]] = None,
        tokenizer: Optional[Any] = None
    ) -> Any:
        """Prépare les données pour le modèle"""
        if tokenizer is None:
            tokenizer = self._get_tokenizer()

        encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=self.config.max_length,
            return_tensors='pt'
        )

        if labels is not None:
            encodings['labels'] = torch.tensor(labels)

        return encodings

    def fit(
        self,
        texts: List[str],
        labels: List[int],
        validation_texts: Optional[List[str]] = None,
        validation_labels: Optional[List[int]] = None,
        **kwargs
    ) -> 'FinBERT':
        """
        Fine-tune le modèle FinBERT.

        Args:
            texts: Textes d'entraînement
            labels: Labels d'entraînement
            validation_texts: Textes de validation (optionnel)
            validation_labels: Labels de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            FinBERT: Instance entraînée
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")

        if len(texts) != len(labels):
            raise ValueError("Les textes et labels doivent avoir la même longueur")

        self.config.num_labels = len(set(labels))

        self.model = _FinBERTModel(self.config).to(self.device)
        tokenizer = self._get_tokenizer()

        train_encodings = self._prepare_dataset(texts, labels, tokenizer)
        train_dataset = self._create_torch_dataset(train_encodings)

        val_dataset = None
        if validation_texts is not None and validation_labels is not None:
            val_encodings = self._prepare_dataset(validation_texts, validation_labels, tokenizer)
            val_dataset = self._create_torch_dataset(val_encodings)

        from transformers import Trainer, TrainingArguments

        training_args = TrainingArguments(
            output_dir='./finbert_results',
            num_train_epochs=kwargs.get('epochs', self.config.epochs),
            per_device_train_batch_size=kwargs.get('batch_size', self.config.batch_size),
            per_device_eval_batch_size=kwargs.get('batch_size', self.config.batch_size),
            warmup_steps=kwargs.get('warmup_steps', self.config.warmup_steps),
            weight_decay=self.config.weight_decay,
            logging_dir='./finbert_logs',
            logging_steps=self.config.logging_steps,
            evaluation_strategy=self.config.evaluation_strategy if val_dataset else 'no',
            save_steps=self.config.save_steps,
            eval_steps=self.config.eval_steps if val_dataset else None,
            load_best_model_at_end=self.config.load_best_model_at_end if val_dataset else False,
            metric_for_best_model=self.config.metric_for_best_model,
            greater_is_better=self.config.greater_is_better,
            report_to='none',
            overwrite_output_dir=True,
            save_total_limit=2,
            seed=42,
        )

        trainer = Trainer(
            model=self.model.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=self._compute_metrics if val_dataset else None,
        )

        logger.info(f"Début du fine-tuning pour {training_args.num_train_epochs} époques")

        trainer.train()

        self.is_fitted = True
        logger.info("Fine-tuning terminé")

        return self

    def _create_torch_dataset(self, encodings):
        """Crée un dataset PyTorch à partir des encodages"""
        import torch
        from torch.utils.data import Dataset

        class FinBERTDataset(Dataset):
            def __init__(self, encodings):
                self.encodings = encodings

            def __getitem__(self, idx):
                item = {key: val[idx] for key, val in self.encodings.items()}
                return item

            def __len__(self):
                return len(self.encodings['input_ids'])

        return FinBERTDataset(encodings)

    def _compute_metrics(self, eval_pred):
        """Calcule les métriques pour l'évaluation"""
        if not SKLEARN_AVAILABLE:
            return {}

        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)

        accuracy = accuracy_score(labels, predictions)
        f1 = f1_score(labels, predictions, average='weighted')
        precision, recall, _, _ = precision_recall_fscore_support(labels, predictions, average='weighted')

        return {
            'accuracy': accuracy,
            'f1': f1,
            'precision': precision,
            'recall': recall,
        }

    def predict(
        self,
        texts: Union[str, List[str]],
        return_proba: bool = True,
        return_logits: bool = False,
        return_embeddings: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray], FinBERTResult]:
        """
        Effectue une prédiction avec le modèle FinBERT.

        Args:
            texts: Texte ou liste de textes
            return_proba: Retourner les probabilités
            return_logits: Retourner les logits
            return_embeddings: Retourner les embeddings
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, Probabilités)
            FinBERTResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        if isinstance(texts, str):
            texts = [texts]

        cache_key = hash(str(texts))
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            return self._prediction_cache[cache_key]

        self.model.eval()
        tokenizer = self._get_tokenizer()

        encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=self.config.max_length,
            return_tensors='pt'
        )

        input_ids = encodings['input_ids'].to(self.device)
        attention_mask = encodings['attention_mask'].to(self.device)

        with torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )

        predictions = None
        probabilities = None
        logits = None
        embeddings = None

        if self.config.task == 'sequence_classification':
            logits = outputs.logits.cpu().numpy()
            if self.config.num_labels > 1:
                predictions = np.argmax(logits, axis=1)
            else:
                predictions = (logits > 0).astype(int).flatten()
            if return_proba:
                if self.config.num_labels > 1:
                    probabilities = F.softmax(torch.tensor(logits), dim=1).numpy()
                else:
                    probabilities = 1 / (1 + np.exp(-logits))
        else:
            if hasattr(outputs, 'logits'):
                logits = outputs.logits.cpu().numpy()
            predictions = logits if logits is not None else None

        if return_embeddings and hasattr(outputs, 'hidden_states'):
            hidden_states = outputs.hidden_states
            embeddings = hidden_states[-1].mean(dim=1).cpu().numpy()

        result = FinBERTResult(
            predictions=predictions,
            probabilities=probabilities,
            logits=logits,
            embeddings=embeddings,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
            metrics=self.metrics,
        )

        self._prediction_cache[cache_key] = result

        if return_details:
            return result
        elif return_proba and predictions is not None:
            return predictions, probabilities
        else:
            return predictions if predictions is not None else logits

    def predict_sentiment(self, texts: List[str]) -> Dict[str, Any]:
        """
        Analyse le sentiment des textes financiers.

        Args:
            texts: Liste de textes

        Returns:
            Dict[str, Any]: Résultats d'analyse de sentiment
        """
        predictions, probabilities = self.predict(texts, return_proba=True)

        sentiment_labels = ['negative', 'neutral', 'positive']
        if self.config.num_labels == 2:
            sentiment_labels = ['negative', 'positive']

        results = []
        for i, text in enumerate(texts):
            pred = predictions[i]
            sentiment = sentiment_labels[pred] if pred < len(sentiment_labels) else 'unknown'
            results.append({
                'text': text,
                'sentiment': sentiment,
                'confidence': probabilities[i].max() if len(probabilities[i]) > 0 else 0,
                'scores': {
                    label: float(probabilities[i][j]) if j < len(probabilities[i]) else 0
                    for j, label in enumerate(sentiment_labels)
                }
            })

        return {
            'results': results,
            'summary': {
                'total': len(results),
                'positive': sum(1 for r in results if r['sentiment'] == 'positive'),
                'neutral': sum(1 for r in results if r['sentiment'] == 'neutral'),
                'negative': sum(1 for r in results if r['sentiment'] == 'negative'),
                'average_confidence': np.mean([r['confidence'] for r in results]),
                'sentiment_score': np.mean([r['scores'].get('positive', 0) - r['scores'].get('negative', 0) for r in results]),
            }
        }

    def extract_financial_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrait les entités financières d'un texte.

        Args:
            text: Texte à analyser

        Returns:
            List[Dict[str, Any]]: Entités financières
        """
        if self.config.task != 'token_classification':
            logger.warning("Le modèle n'est pas configuré pour l'extraction d'entités")

        tokenizer = self._get_tokenizer()
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=self.config.max_length).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        logits = outputs.logits.cpu().numpy()[0]
        predictions = np.argmax(logits, axis=-1)

        tokens = tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])

        entities = []
        current_entity = None
        current_tokens = []

        for token, pred in zip(tokens, predictions):
            if pred > 0:
                if current_entity is None:
                    current_entity = pred
                    current_tokens = [token]
                else:
                    current_tokens.append(token)
            else:
                if current_entity is not None:
                    entity_text = tokenizer.convert_tokens_to_string(current_tokens)
                    entities.append({
                        'text': entity_text,
                        'type': f'FINANCIAL_ENTITY_{current_entity}',
                        'tokens': current_tokens,
                    })
                    current_entity = None
                    current_tokens = []

        if current_entity is not None:
            entity_text = tokenizer.convert_tokens_to_string(current_tokens)
            entities.append({
                'text': entity_text,
                'type': f'FINANCIAL_ENTITY_{current_entity}',
                'tokens': current_tokens,
            })

        return entities

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Extrait les embeddings des textes.

        Args:
            texts: Liste de textes

        Returns:
            np.ndarray: Embeddings
        """
        result = self.predict(texts, return_embeddings=True, return_details=True)
        return result.embeddings

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_fitted': self.is_fitted,
            'loss_history_length': len(self.loss_history),
            'val_loss_history_length': len(self.val_loss_history),
            'device': str(self.device),
            'task': self.config.task,
            'num_labels': self.config.num_labels,
            'model_name': self.config.model_name,
            'max_length': self.config.max_length,
        }

        if self.loss_history:
            metrics['final_loss'] = self.loss_history[-1]
            metrics['min_loss'] = min(self.loss_history)

        if self.val_loss_history:
            metrics['final_val_loss'] = self.val_loss_history[-1]
            metrics['min_val_loss'] = min(self.val_loss_history)

        metrics.update(self.metrics)

        return metrics

    def save(self, filepath: str) -> bool:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'model_state_dict': self.model.state_dict() if self.model else None,
                'is_fitted': self.is_fitted,
                'loss_history': self.loss_history,
                'val_loss_history': self.val_loss_history,
                'metrics': self.metrics,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            if self.model is not None:
                model_path = filepath.replace('.pkl', '_transformers')
                os.makedirs(model_path, exist_ok=True)
                self.model.model.save_pretrained(model_path)
                self._get_tokenizer().save_pretrained(model_path)

            logger.info(f"Modèle sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'FinBERT':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = FinBERTConfig(**data['config'])
            model = cls(config)

            model_path = filepath.replace('.pkl', '_transformers')
            if os.path.exists(model_path):
                model.model = _FinBERTModel(config)
                model.model.model = AutoModelForSequenceClassification.from_pretrained(model_path)
                model.model.to(model.device)

            model.is_fitted = data.get('is_fitted', False)
            model.loss_history = data.get('loss_history', [])
            model.val_loss_history = data.get('val_loss_history', [])
            model.metrics = data.get('metrics', {})

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_finbert(
    model_name: str = "ProsusAI/finbert",
    task: str = 'sequence_classification',
    num_labels: int = 3,
    max_length: int = 512,
    epochs: int = 3,
    **kwargs
) -> FinBERT:
    config = FinBERTConfig(
        model_name=model_name,
        task=task,
        num_labels=num_labels,
        max_length=max_length,
        epochs=epochs,
        **kwargs
    )
    return FinBERT(config)


__all__ = [
    'FinBERT',
    'FinBERTConfig',
    'FinBERTResult',
    'create_finbert',
]

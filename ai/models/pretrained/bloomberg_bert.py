
# ai/models/pretrained/bloomberg_bert.py
"""
NEXUS AI TRADING SYSTEM - Bloomberg BERT Model
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
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BloombergBERTConfig:
    model_name: str = "bloomberg/FinBERT"
    pretrained: bool = True
    max_length: int = 512
    batch_size: int = 32
    learning_rate: float = 2e-5
    epochs: int = 3
    warmup_steps: int = 0
    weight_decay: float = 0.01
    dropout: float = 0.1
    use_gpu: bool = False
    num_labels: int = 2
    task: str = 'sequence_classification'
    fine_tune: bool = True
    output_hidden_states: bool = False
    output_attentions: bool = False

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
        }


@dataclass
class BloombergBERTResult:
    predictions: np.ndarray
    probabilities: Optional[np.ndarray] = None
    logits: Optional[np.ndarray] = None
    hidden_states: Optional[List[np.ndarray]] = None
    attentions: Optional[List[np.ndarray]] = None
    embeddings: Optional[np.ndarray] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
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
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
        }


class _BloombergBERTModel(nn.Module):
    """Wrapper pour le modèle Bloomberg BERT"""

    def __init__(self, config: BloombergBERTConfig):
        super().__init__()
        self.config = config

        if config.task == 'sequence_classification':
            self.model = AutoModelForSequenceClassification.from_pretrained(
                config.model_name,
                num_labels=config.num_labels,
                output_hidden_states=config.output_hidden_states,
                output_attentions=config.output_attentions,
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

        # Dropout personnalisé
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, input_ids, attention_mask, token_type_ids=None, labels=None):
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            labels=labels,
        )

        return outputs


class BloombergBERT:
    """
    Bloomberg BERT (FinBERT) model for financial NLP tasks.

    This implementation provides a wrapper around the Bloomberg FinBERT model
    for financial text analysis, sentiment analysis, and classification.

    Features:
    - Financial text classification
    - Sentiment analysis on financial news
    - Named entity recognition in financial texts
    - Question answering on financial documents
    - Fine-tuning capabilities
    - GPU acceleration
    - Batch processing

    Example:
        ```python
        config = BloombergBERTConfig(
            model_name="bloomberg/FinBERT",
            task='sequence_classification',
            num_labels=3,
            max_length=512,
            epochs=3
        )
        model = BloombergBERT(config)

        # Fine-tune
        model.fit(train_texts, train_labels)

        # Predict
        predictions, probabilities = model.predict(["Market sentiment is positive"])
        ```
    """

    def __init__(self, config: Optional[BloombergBERTConfig] = None):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers est requis. Installez avec: pip install transformers")

        self.config = config or BloombergBERTConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_BloombergBERTModel] = None
        self.tokenizer: Optional[Any] = None
        self.is_fitted = False
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []

        logger.info(f"BloombergBERT initialisé sur {self.device}")

    def _get_tokenizer(self) -> Any:
        """Retourne le tokenizer Bloomberg BERT"""
        if self.tokenizer is None:
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        return self.tokenizer

    def _prepare_data(
        self,
        texts: List[str],
        labels: Optional[List[int]] = None,
        batch_size: Optional[int] = None
    ) -> Any:
        """Prépare les données pour le modèle"""
        tokenizer = self._get_tokenizer()
        max_length = self.config.max_length

        if batch_size is None:
            batch_size = self.config.batch_size

        encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors='pt'
        )

        dataset = []
        for i in range(len(texts)):
            item = {
                'input_ids': encodings['input_ids'][i],
                'attention_mask': encodings['attention_mask'][i],
            }
            if labels is not None:
                item['labels'] = torch.tensor(labels[i])
            dataset.append(item)

        return dataset

    def fit(
        self,
        texts: List[str],
        labels: List[int],
        validation_texts: Optional[List[str]] = None,
        validation_labels: Optional[List[int]] = None,
        **kwargs
    ) -> 'BloombergBERT':
        """
        Fine-tune le modèle Bloomberg BERT.

        Args:
            texts: Textes d'entraînement
            labels: Labels d'entraînement
            validation_texts: Textes de validation (optionnel)
            validation_labels: Labels de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            BloombergBERT: Instance entraînée
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers n'est pas installé")

        if len(texts) != len(labels):
            raise ValueError("Les textes et labels doivent avoir la même longueur")

        self.config.num_labels = len(set(labels))

        # Création du modèle
        self.model = _BloombergBERTModel(self.config).to(self.device)

        # Préparation des données
        train_data = self._prepare_data(texts, labels)
        val_data = None
        if validation_texts is not None and validation_labels is not None:
            val_data = self._prepare_data(validation_texts, validation_labels)

        # Optimiseur
        from transformers import AdamW, get_linear_schedule_with_warmup

        optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )

        epochs = kwargs.get('epochs', self.config.epochs)
        batch_size = kwargs.get('batch_size', self.config.batch_size)
        warmup_steps = kwargs.get('warmup_steps', self.config.warmup_steps)

        num_training_steps = len(train_data) * epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=warmup_steps,
            num_training_steps=num_training_steps
        )

        # Entraînement
        self.loss_history = []
        self.val_loss_history = []
        best_val_loss = float('inf')

        logger.info(f"Début du fine-tuning pour {epochs} époques")

        for epoch in range(epochs):
            self.model.train()
            epoch_loss = 0.0

            # Shuffle des données
            import random
            indices = list(range(len(train_data)))
            random.shuffle(indices)

            for i in range(0, len(indices), batch_size):
                batch_indices = indices[i:i + batch_size]
                batch = [train_data[idx] for idx in batch_indices]

                input_ids = torch.stack([item['input_ids'] for item in batch]).to(self.device)
                attention_mask = torch.stack([item['attention_mask'] for item in batch]).to(self.device)
                labels_batch = torch.stack([item['labels'] for item in batch]).to(self.device)

                optimizer.zero_grad()

                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels_batch
                )

                loss = outputs.loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()

                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(indices)
            self.loss_history.append(avg_loss)

            # Validation
            val_loss = None
            if val_data:
                self.model.eval()
                val_loss = 0.0

                with torch.no_grad():
                    for i in range(0, len(val_data), batch_size):
                        batch = val_data[i:i + batch_size]

                        input_ids = torch.stack([item['input_ids'] for item in batch]).to(self.device)
                        attention_mask = torch.stack([item['attention_mask'] for item in batch]).to(self.device)
                        labels_batch = torch.stack([item['labels'] for item in batch]).to(self.device)

                        outputs = self.model(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                            labels=labels_batch
                        )

                        val_loss += outputs.loss.item()

                val_loss = val_loss / len(val_data)
                self.val_loss_history.append(val_loss)

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    self._save_checkpoint()

            log_msg = f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}"
            if val_loss is not None:
                log_msg += f", Val Loss: {val_loss:.6f}"
            logger.info(log_msg)

        # Charger le meilleur modèle
        if val_data:
            self._load_checkpoint()

        self.is_fitted = True
        logger.info("Fine-tuning terminé")

        return self

    def _save_checkpoint(self):
        if self.model is None:
            return

        self._checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
        }

    def _load_checkpoint(self):
        if hasattr(self, '_checkpoint') and self.model is not None:
            self.model.load_state_dict(self._checkpoint['model_state_dict'])

    def predict(
        self,
        texts: Union[str, List[str]],
        return_proba: bool = True,
        return_logits: bool = False,
        return_embeddings: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray], BloombergBERTResult]:
        """
        Effectue une prédiction avec le modèle Bloomberg BERT.

        Args:
            texts: Texte ou liste de textes
            return_proba: Retourner les probabilités
            return_logits: Retourner les logits
            return_embeddings: Retourner les embeddings
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, Probabilités)
            BloombergBERTResult: Résultat complet
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
            predictions = np.argmax(logits, axis=1)
            if return_proba:
                probabilities = F.softmax(torch.tensor(logits), dim=1).numpy()
        else:
            # Pour d'autres tâches
            if hasattr(outputs, 'logits'):
                logits = outputs.logits.cpu().numpy()
            predictions = logits if logits is not None else None

        # Extraire les embeddings si demandé
        if return_embeddings and hasattr(outputs, 'hidden_states'):
            hidden_states = outputs.hidden_states
            embeddings = hidden_states[-1].mean(dim=1).cpu().numpy()

        result = BloombergBERTResult(
            predictions=predictions,
            probabilities=probabilities,
            logits=logits,
            embeddings=embeddings,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
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

        results = []
        for i, text in enumerate(texts):
            sentiment = 'positive' if predictions[i] == 1 else 'negative' if predictions[i] == 0 else 'neutral'
            results.append({
                'text': text,
                'sentiment': sentiment,
                'confidence': probabilities[i].max(),
                'scores': {
                    'negative': probabilities[i][0] if len(probabilities[i]) > 0 else 0,
                    'neutral': probabilities[i][1] if len(probabilities[i]) > 1 else 0,
                    'positive': probabilities[i][2] if len(probabilities[i]) > 2 else 0,
                }
            })

        return {
            'results': results,
            'average_sentiment': np.mean([r['scores']['positive'] - r['scores']['negative'] for r in results]),
        }

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
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Sauvegarder également le modèle au format transformers
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
    def load(cls, filepath: str) -> 'BloombergBERT':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = BloombergBERTConfig(**data['config'])
            model = cls(config)

            # Charger le modèle transformers
            model_path = filepath.replace('.pkl', '_transformers')
            if os.path.exists(model_path):
                model.model = _BloombergBERTModel(config)
                model.model.model = AutoModelForSequenceClassification.from_pretrained(model_path)
                model.model.to(model.device)

            model.is_fitted = data.get('is_fitted', False)
            model.loss_history = data.get('loss_history', [])
            model.val_loss_history = data.get('val_loss_history', [])

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_bloomberg_bert(
    model_name: str = "bloomberg/FinBERT",
    task: str = 'sequence_classification',
    num_labels: int = 3,
    max_length: int = 512,
    epochs: int = 3,
    **kwargs
) -> BloombergBERT:
    config = BloombergBERTConfig(
        model_name=model_name,
        task=task,
        num_labels=num_labels,
        max_length=max_length,
        epochs=epochs,
        **kwargs
    )
    return BloombergBERT(config)


__all__ = [
    'BloombergBERT',
    'BloombergBERTConfig',
    'BloombergBERTResult',
    'create_bloomberg_bert',
]

# ai/models/ensemble/bagging_ensemble.py
"""
NEXUS AI TRADING SYSTEM - Bagging Ensemble Model
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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

try:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
    from sklearn.metrics import mean_squared_error, r2_score, accuracy_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BaggingConfig:
    n_estimators: int = 10
    max_samples: Optional[Union[int, float]] = None
    max_features: Optional[Union[int, float]] = None
    bootstrap: bool = True
    bootstrap_features: bool = False
    oob_score: bool = False
    n_jobs: int = -1
    random_state: Optional[int] = 42
    verbose: int = 0
    base_model_type: str = 'decision_tree'
    base_model_config: Dict[str, Any] = field(default_factory=dict)
    aggregation_method: str = 'mean'
    validation_ratio: float = 0.0
    early_stopping: bool = False
    patience: int = 5
    use_gpu: bool = False
    batch_size: int = 256
    learning_rate: float = 0.001
    epochs: int = 100
    warm_start: bool = False

    def __post_init__(self):
        if isinstance(self.max_samples, float):
            if not 0 < self.max_samples <= 1:
                raise ValueError("max_samples float doit être entre 0 et 1")
        elif self.max_samples is not None and self.max_samples < 1:
            raise ValueError("max_samples doit être >= 1")
        
        if isinstance(self.max_features, float):
            if not 0 < self.max_features <= 1:
                raise ValueError("max_features float doit être entre 0 et 1")
        
        if self.validation_ratio < 0 or self.validation_ratio >= 1:
            raise ValueError("validation_ratio doit être entre 0 et 1")


@dataclass
class BaggingResult:
    predictions: np.ndarray
    individual_predictions: List[np.ndarray]
    weights: Optional[np.ndarray] = None
    confidence: Optional[np.ndarray] = None
    variance: Optional[np.ndarray] = None
    oob_score: Optional[float] = None
    feature_importance: Optional[np.ndarray] = None
    model_metrics: Optional[Dict[str, float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'individual_predictions': [p.tolist() if isinstance(p, np.ndarray) else p for p in self.individual_predictions],
            'weights': self.weights.tolist() if isinstance(self.weights, np.ndarray) else self.weights,
            'confidence': self.confidence.tolist() if isinstance(self.confidence, np.ndarray) else self.confidence,
            'variance': self.variance.tolist() if isinstance(self.variance, np.ndarray) else self.variance,
            'oob_score': self.oob_score,
            'feature_importance': self.feature_importance.tolist() if isinstance(self.feature_importance, np.ndarray) else self.feature_importance,
            'model_metrics': self.model_metrics,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
        }


class BaggingEnsemble:
    
    def __init__(self, config: Optional[BaggingConfig] = None):
        self.config = config or BaggingConfig()
        self.models: List[Any] = []
        self.model_weights: np.ndarray = np.array([])
        self.feature_importance: Optional[np.ndarray] = None
        self.oob_indices: List[np.ndarray] = []
        self.oob_scores: List[float] = []
        self.training_metrics: List[Dict[str, float]] = []
        self.is_fitted = False
        self.n_features = 0
        self.n_samples = 0
        self._thread_local = threading.local()
        self._lock = threading.Lock()
        self._prediction_cache: Dict[str, Any] = {}
        self.oob_score = None
        
        logger.info(f"BaggingEnsemble initialisé avec {self.config.n_estimators} estimateurs")
    
    def _get_random_state(self, seed: Optional[int] = None) -> np.random.RandomState:
        if seed is None:
            seed = self.config.random_state
        if seed is not None:
            return np.random.RandomState(seed)
        return np.random.RandomState()
    
    def _create_base_model(self, seed: Optional[int] = None) -> Any:
        model_type = self.config.base_model_type.lower()
        config = self.config.base_model_config.copy()
        
        if seed is not None and 'random_state' not in config:
            config['random_state'] = seed
        
        if model_type == 'decision_tree' and SKLEARN_AVAILABLE:
            return DecisionTreeRegressor(**config) if self._is_regression() else DecisionTreeClassifier(**config)
        
        elif model_type == 'random_forest' and SKLEARN_AVAILABLE:
            return RandomForestRegressor(**config) if self._is_regression() else RandomForestClassifier(**config)
        
        elif model_type == 'xgboost' and XGB_AVAILABLE:
            if self._is_regression():
                return xgb.XGBRegressor(**config)
            else:
                return xgb.XGBClassifier(**config)
        
        elif model_type == 'lightgbm' and LGB_AVAILABLE:
            if self._is_regression():
                return lgb.LGBMRegressor(**config)
            else:
                return lgb.LGBMClassifier(**config)
        
        elif model_type == 'torch' and TORCH_AVAILABLE:
            return self._create_torch_model(config)
        
        else:
            raise ValueError(f"Modèle de base non supporté: {model_type}")
    
    def _create_torch_model(self, config: Dict[str, Any]) -> Any:
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        
        import torch.nn as nn
        
        class SimpleTorchModel(nn.Module):
            def __init__(self, input_dim, hidden_dims=[64, 32], output_dim=1):
                super().__init__()
                layers = []
                prev_dim = input_dim
                for hidden_dim in hidden_dims:
                    layers.append(nn.Linear(prev_dim, hidden_dim))
                    layers.append(nn.ReLU())
                    layers.append(nn.Dropout(0.1))
                    prev_dim = hidden_dim
                layers.append(nn.Linear(prev_dim, output_dim))
                self.network = nn.Sequential(*layers)
            
            def forward(self, x):
                return self.network(x)
        
        input_dim = config.get('input_dim', self.n_features)
        hidden_dims = config.get('hidden_dims', [64, 32])
        output_dim = config.get('output_dim', 1)
        
        return SimpleTorchModel(input_dim, hidden_dims, output_dim)
    
    def _is_regression(self) -> bool:
        return True
    
    def _get_bootstrap_samples(self, X: np.ndarray, y: np.ndarray, indices: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_samples = X.shape[0]
        
        if self.config.max_samples is None:
            sample_size = n_samples
        elif isinstance(self.config.max_samples, float):
            sample_size = int(n_samples * self.config.max_samples)
        else:
            sample_size = min(self.config.max_samples, n_samples)
        
        rng = self._get_random_state()
        if self.config.bootstrap:
            indices_bootstrap = rng.choice(n_samples, size=sample_size, replace=True)
        else:
            indices_bootstrap = rng.choice(n_samples, size=sample_size, replace=False)
        
        oob_indices = np.setdiff1d(np.arange(n_samples), indices_bootstrap)
        
        if self.config.bootstrap_features and self.config.max_features is not None:
            n_features = X.shape[1]
            if isinstance(self.config.max_features, float):
                feature_size = int(n_features * self.config.max_features)
            else:
                feature_size = min(self.config.max_features, n_features)
            feature_indices = rng.choice(n_features, size=feature_size, replace=False)
            X_bootstrap = X[indices_bootstrap][:, feature_indices]
        else:
            X_bootstrap = X[indices_bootstrap]
        
        y_bootstrap = y[indices_bootstrap]
        
        return X_bootstrap, y_bootstrap, oob_indices
    
    def _train_model(self, model: Any, X: np.ndarray, y: np.ndarray, X_val: Optional[np.ndarray] = None, y_val: Optional[np.ndarray] = None, model_id: int = 0) -> Dict[str, Any]:
        metrics = {
            'model_id': model_id,
            'train_time': 0.0,
            'train_score': None,
            'val_score': None,
            'oob_score': None,
            'n_samples': len(X),
            'n_features': X.shape[1] if len(X.shape) > 1 else 1,
        }
        
        start_time = datetime.now()
        
        try:
            model_type = self.config.base_model_type.lower()
            
            if model_type == 'torch' and TORCH_AVAILABLE:
                metrics.update(self._train_torch_model(model, X, y, X_val, y_val))
            else:
                if model_type in ['xgboost', 'lightgbm'] and X_val is not None and self.config.early_stopping:
                    eval_set = [(X_val, y_val)]
                    if model_type == 'xgboost':
                        model.fit(X, y, eval_set=eval_set, early_stopping_rounds=self.config.patience, verbose=False)
                    else:
                        model.fit(X, y, eval_set=eval_set, callbacks=[lgb.early_stopping(self.config.patience)] if LGB_AVAILABLE else None, verbose=False)
                else:
                    model.fit(X, y)
                
                metrics['train_score'] = self._evaluate_model(model, X, y)
                if X_val is not None:
                    metrics['val_score'] = self._evaluate_model(model, X_val, y_val)
            
            metrics['train_time'] = (datetime.now() - start_time).total_seconds()
            
        except Exception as e:
            logger.error(f"Erreur d'entraînement du modèle {model_id}: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def _train_torch_model(self, model: Any, X: np.ndarray, y: np.ndarray, X_val: Optional[np.ndarray] = None, y_val: Optional[np.ndarray] = None) -> Dict[str, Any]:
        if not TORCH_AVAILABLE:
            return {}
        
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import DataLoader, TensorDataset
        
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y).reshape(-1, 1)
        
        dataset = TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)
        
        optimizer = optim.Adam(model.parameters(), lr=self.config.learning_rate)
        criterion = nn.MSELoss()
        
        if self.config.use_gpu and torch.cuda.is_available():
            model = model.cuda()
            device = torch.device('cuda')
        else:
            device = torch.device('cpu')
        
        train_losses = []
        val_losses = []
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.config.epochs):
            model.train()
            epoch_loss = 0
            for batch_X, batch_y in dataloader:
                batch_X = batch_X.to(device)
                batch_y = batch_y.to(device)
                
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
            
            avg_train_loss = epoch_loss / len(dataloader)
            train_losses.append(avg_train_loss)
            
            if X_val is not None and y_val is not None:
                model.eval()
                with torch.no_grad():
                    X_val_tensor = torch.FloatTensor(X_val).to(device)
                    y_val_tensor = torch.FloatTensor(y_val).reshape(-1, 1).to(device)
                    val_outputs = model(X_val_tensor)
                    val_loss = criterion(val_outputs, y_val_tensor)
                    val_losses.append(val_loss.item())
                
                if self.config.early_stopping:
                    if val_loss < best_val_loss:
                        best_val_loss = val_loss
                        patience_counter = 0
                    else:
                        patience_counter += 1
                        if patience_counter >= self.config.patience:
                            logger.info(f"Arrêt précoce à l'époque {epoch}")
                            break
        
        model.eval()
        with torch.no_grad():
            X_tensor = X_tensor.to(device)
            predictions = model(X_tensor).cpu().numpy().flatten()
            train_score = 1 - np.mean((predictions - y) ** 2) / np.var(y)
        
        return {
            'train_score': train_score,
            'train_losses': train_losses,
            'val_losses': val_losses,
            'epochs_trained': len(train_losses),
        }
    
    def _evaluate_model(self, model: Any, X: np.ndarray, y: np.ndarray) -> float:
        try:
            predictions = model.predict(X)
            if self._is_regression():
                return r2_score(y, predictions)
            else:
                return accuracy_score(y, predictions)
        except:
            return 0.0
    
    def _compute_oob_score(self, X: np.ndarray, y: np.ndarray) -> float:
        if not self.oob_indices:
            return 0.0
        
        oob_predictions = defaultdict(list)
        
        for model_idx, oob_indices in enumerate(self.oob_indices):
            if len(oob_indices) > 0:
                model = self.models[model_idx]
                try:
                    X_oob = X[oob_indices]
                    preds = model.predict(X_oob)
                    for idx, pred in zip(oob_indices, preds):
                        oob_predictions[idx].append(pred)
                except:
                    continue
        
        y_pred_oob = np.array([
            np.mean(preds) if preds else 0.0 
            for preds in oob_predictions.values()
        ])
        
        if len(y_pred_oob) > 0:
            return r2_score(y[:len(y_pred_oob)], y_pred_oob)
        return 0.0
    
    def _aggregate_predictions(self, individual_preds: List[np.ndarray], weights: Optional[np.ndarray] = None) -> np.ndarray:
        if not individual_preds:
            raise ValueError("Aucune prédiction à agréger")
        
        if weights is None:
            weights = np.ones(len(individual_preds)) / len(individual_preds)
        
        weights = np.array(weights)
        if len(weights) != len(individual_preds):
            raise ValueError("Nombre de poids différent du nombre de modèles")
        
        aggregation_method = self.config.aggregation_method
        
        if aggregation_method == 'mean':
            return np.mean(individual_preds, axis=0)
        
        elif aggregation_method == 'median':
            return np.median(individual_preds, axis=0)
        
        elif aggregation_method == 'weighted':
            weights_norm = weights / weights.sum()
            weighted_preds = np.array(individual_preds) * weights_norm[:, np.newaxis]
            return np.sum(weighted_preds, axis=0)
        
        elif aggregation_method == 'voting':
            if self._is_regression():
                logger.warning("Voting utilisé pour la régression, passage à la moyenne")
                return np.mean(individual_preds, axis=0)
            else:
                rounded_preds = np.round(np.array(individual_preds))
                return np.apply_along_axis(
                    lambda x: np.bincount(x.astype(int)).argmax(), 
                    axis=0, 
                    arr=rounded_preds
                )
        
        else:
            raise ValueError(f"Méthode d'agrégation non supportée: {aggregation_method}")
    
    def _compute_confidence(self, individual_preds: List[np.ndarray], weights: Optional[np.ndarray] = None) -> np.ndarray:
        if len(individual_preds) < 2:
            return np.ones_like(individual_preds[0])
        
        if weights is None:
            weights = np.ones(len(individual_preds)) / len(individual_preds)
        
        weights_norm = np.array(weights) / np.sum(weights)
        weighted_mean = np.average(individual_preds, axis=0, weights=weights_norm)
        variance = np.average(
            [(pred - weighted_mean) ** 2 for pred in individual_preds],
            axis=0,
            weights=weights_norm
        )
        
        if np.std(individual_preds) > 0:
            confidence = 1 - np.sqrt(variance) / (np.std(individual_preds) + 1e-6)
            confidence = np.clip(confidence, 0, 1)
        else:
            confidence = np.ones_like(weighted_mean)
        
        return confidence
    
    def _compute_feature_importance(self) -> Optional[np.ndarray]:
        importances = []
        
        for model in self.models:
            try:
                if hasattr(model, 'feature_importances_'):
                    importances.append(model.feature_importances_)
                elif hasattr(model, 'coef_'):
                    importances.append(np.abs(model.coef_).flatten())
            except:
                continue
        
        if importances:
            agg_importance = np.mean(importances, axis=0)
            if agg_importance.sum() > 0:
                agg_importance = agg_importance / agg_importance.sum()
            return agg_importance
        
        return None
    
    def _compute_model_weights(self) -> np.ndarray:
        scores = []
        for metrics in self.training_metrics:
            if 'val_score' in metrics and metrics['val_score'] is not None:
                score = metrics['val_score']
            elif 'train_score' in metrics and metrics['train_score'] is not None:
                score = metrics['train_score']
            else:
                score = 0.0
            
            weight = max(score, 0.1) + 0.1
            scores.append(weight)
        
        weights = np.array(scores)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        
        return weights
    
    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series], sample_weight: Optional[np.ndarray] = None) -> 'BaggingEnsemble':
        if isinstance(X, pd.DataFrame):
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values
        
        self.n_samples, self.n_features = X.shape
        self.models = []
        self.oob_indices = []
        self.training_metrics = []
        
        logger.info(f"Début de l'entraînement avec {self.config.n_estimators} modèles")
        start_time = datetime.now()
        
        X_train, y_train = X, y
        X_val, y_val = None, None
        
        if self.config.validation_ratio > 0:
            n_val = int(self.n_samples * self.config.validation_ratio)
            indices = np.random.permutation(self.n_samples)
            val_indices = indices[:n_val]
            train_indices = indices[n_val:]
            
            X_train, y_train = X[train_indices], y[train_indices]
            X_val, y_val = X[val_indices], y[val_indices]
        
        if self.config.n_jobs > 1:
            with ThreadPoolExecutor(max_workers=self.config.n_jobs) as executor:
                futures = []
                for i in range(self.config.n_estimators):
                    seed = self.config.random_state + i if self.config.random_state is not None else None
                    X_boot, y_boot, oob_idx = self._get_bootstrap_samples(X_train, y_train)
                    self.oob_indices.append(oob_idx)
                    model = self._create_base_model(seed)
                    future = executor.submit(self._train_model, model, X_boot, y_boot, X_val, y_val, i)
                    futures.append((model, future))
                
                for model, future in futures:
                    try:
                        metrics = future.result(timeout=300)
                        self.models.append(model)
                        self.training_metrics.append(metrics)
                    except Exception as e:
                        logger.error(f"Erreur dans l'entraînement parallèle: {e}")
                        continue
        else:
            for i in range(self.config.n_estimators):
                seed = self.config.random_state + i if self.config.random_state is not None else None
                X_boot, y_boot, oob_idx = self._get_bootstrap_samples(X_train, y_train)
                self.oob_indices.append(oob_idx)
                model = self._create_base_model(seed)
                metrics = self._train_model(model, X_boot, y_boot, X_val, y_val, i)
                self.models.append(model)
                self.training_metrics.append(metrics)
                
                if self.config.verbose > 0 and (i + 1) % 10 == 0:
                    logger.info(f"Modèle {i + 1}/{self.config.n_estimators} entraîné")
        
        self.model_weights = self._compute_model_weights()
        
        if self.config.oob_score:
            self.oob_score = self._compute_oob_score(X_train, y_train)
        
        self.feature_importance = self._compute_feature_importance()
        self.is_fitted = True
        training_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Entraînement terminé en {training_time:.2f}s")
        logger.info(f"Nombre de modèles: {len(self.models)}")
        if hasattr(self, 'oob_score') and self.oob_score is not None:
            logger.info(f"Score OOB: {self.oob_score:.4f}")
        
        return self
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame], return_details: bool = False) -> Union[np.ndarray, BaggingResult]:
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        cache_key = str(hash(X.tobytes()))
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            return self._prediction_cache[cache_key]
        
        individual_preds = []
        
        for model in self.models:
            try:
                pred = model.predict(X)
                individual_preds.append(pred)
            except Exception as e:
                logger.error(f"Erreur de prédiction pour un modèle: {e}")
                continue
        
        if not individual_preds:
            raise RuntimeError("Aucun modèle n'a pu effectuer de prédiction")
        
        predictions = self._aggregate_predictions(individual_preds, self.model_weights)
        confidence = self._compute_confidence(individual_preds, self.model_weights)
        variance = np.var(individual_preds, axis=0) if len(individual_preds) > 1 else np.zeros_like(predictions)
        
        result = BaggingResult(
            predictions=predictions,
            individual_predictions=individual_preds,
            weights=self.model_weights,
            confidence=confidence,
            variance=variance,
            oob_score=self.oob_score if hasattr(self, 'oob_score') else None,
            feature_importance=self.feature_importance,
            model_metrics={
                'n_models': len(self.models),
                'oob_score': self.oob_score if hasattr(self, 'oob_score') else None,
            },
        )
        
        self._prediction_cache[cache_key] = result if return_details else predictions
        
        return result if return_details else predictions
    
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")
        
        if self._is_regression():
            raise ValueError("predict_proba n'est pas supporté pour la régression")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        probas = []
        for model in self.models:
            if hasattr(model, 'predict_proba'):
                probas.append(model.predict_proba(X))
        
        if not probas:
            raise RuntimeError("Aucun modèle ne supporte predict_proba")
        
        if self.config.aggregation_method == 'mean':
            return np.mean(probas, axis=0)
        elif self.config.aggregation_method == 'weighted':
            weights_norm = self.model_weights / self.model_weights.sum()
            weighted_probas = np.array(probas) * weights_norm[:, np.newaxis, np.newaxis]
            return np.sum(weighted_probas, axis=0)
        else:
            return np.mean(probas, axis=0)
    
    def score(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series]) -> float:
        predictions = self.predict(X)
        
        if self._is_regression():
            return r2_score(y, predictions)
        else:
            return accuracy_score(y, np.round(predictions))
    
    def save(self, filepath: str) -> bool:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            data = {
                'config': self.config,
                'models': self.models,
                'model_weights': self.model_weights,
                'oob_indices': self.oob_indices,
                'oob_score': getattr(self, 'oob_score', None),
                'feature_importance': self.feature_importance,
                'training_metrics': self.training_metrics,
                'n_features': self.n_features,
                'n_samples': self.n_samples,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            logger.info(f"Modèle sauvegardé: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    @classmethod
    def load(cls, filepath: str) -> 'BaggingEnsemble':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            ensemble = cls(data['config'])
            ensemble.models = data['models']
            ensemble.model_weights = data['model_weights']
            ensemble.oob_indices = data['oob_indices']
            ensemble.oob_score = data.get('oob_score')
            ensemble.feature_importance = data.get('feature_importance')
            ensemble.training_metrics = data.get('training_metrics', [])
            ensemble.n_features = data['n_features']
            ensemble.n_samples = data['n_samples']
            ensemble.is_fitted = data['is_fitted']
            
            logger.info(f"Modèle chargé: {filepath}")
            return ensemble
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise
    
    def get_params(self) -> Dict[str, Any]:
        return {
            'n_estimators': self.config.n_estimators,
            'max_samples': self.config.max_samples,
            'max_features': self.config.max_features,
            'bootstrap': self.config.bootstrap,
            'bootstrap_features': self.config.bootstrap_features,
            'oob_score': self.config.oob_score,
            'n_jobs': self.config.n_jobs,
            'random_state': self.config.random_state,
            'base_model_type': self.config.base_model_type,
            'aggregation_method': self.config.aggregation_method,
            'n_models_trained': len(self.models),
        }
    
    def get_model_metrics(self) -> Dict[str, Any]:
        metrics = {
            'n_models': len(self.models),
            'n_features': self.n_features,
            'n_samples': self.n_samples,
            'model_weights': self.model_weights.tolist() if self.model_weights is not None else None,
            'oob_score': getattr(self, 'oob_score', None),
            'feature_importance': self.feature_importance.tolist() if self.feature_importance is not None else None,
            'training_metrics': self.training_metrics,
            'config': {
                'n_estimators': self.config.n_estimators,
                'max_samples': self.config.max_samples,
                'max_features': self.config.max_features,
                'bootstrap': self.config.bootstrap,
                'base_model_type': self.config.base_model_type,
                'aggregation_method': self.config.aggregation_method,
            },
            'is_fitted': self.is_fitted,
        }
        
        if self.training_metrics:
            train_scores = [m.get('train_score', 0) for m in self.training_metrics if 'train_score' in m]
            val_scores = [m.get('val_score', 0) for m in self.training_metrics if 'val_score' in m]
            
            metrics['train_score_mean'] = np.mean(train_scores) if train_scores else None
            metrics['train_score_std'] = np.std(train_scores) if train_scores else None
            metrics['val_score_mean'] = np.mean(val_scores) if val_scores else None
            metrics['val_score_std'] = np.std(val_scores) if val_scores else None
        
        return metrics
    
    def get_oob_predictions(self, X: np.ndarray) -> Optional[np.ndarray]:
        if not self.oob_indices:
            return None
        
        oob_preds = []
        for model_idx, oob_idx in enumerate(self.oob_indices):
            if len(oob_idx) > 0:
                model = self.models[model_idx]
                try:
                    preds = model.predict(X[oob_idx])
                    oob_preds.append((oob_idx, preds))
                except:
                    continue
        
        if not oob_preds:
            return None
        
        all_preds = np.zeros(len(X))
        counts = np.zeros(len(X))
        
        for idx, preds in oob_preds:
            all_preds[idx] += preds
            counts[idx] += 1
        
        with np.errstate(divide='ignore', invalid='ignore'):
            oob_predictions = np.divide(all_preds, counts, where=counts > 0)
        
        return oob_predictions


def create_ensemble_from_config(config_dict: Dict[str, Any]) -> BaggingEnsemble:
    config = BaggingConfig(**config_dict)
    return BaggingEnsemble(config)


def create_ensemble_from_args(
    n_estimators: int = 10,
    base_model: str = 'decision_tree',
    aggregation: str = 'mean',
    max_samples: Optional[float] = 0.8,
    max_features: Optional[float] = 0.7,
    bootstrap: bool = True,
    n_jobs: int = -1,
    random_state: Optional[int] = 42,
    **kwargs
) -> BaggingEnsemble:
    config = BaggingConfig(
        n_estimators=n_estimators,
        base_model_type=base_model,
        aggregation_method=aggregation,
        max_samples=max_samples,
        max_features=max_features,
        bootstrap=bootstrap,
        n_jobs=n_jobs,
        random_state=random_state,
        **kwargs
    )
    return BaggingEnsemble(config)


__all__ = [
    'BaggingEnsemble',
    'BaggingConfig',
    'BaggingResult',
    'create_ensemble_from_config',
    'create_ensemble_from_args',
]

# ai/models/ensemble/voting_ensemble.py
"""
NEXUS AI TRADING SYSTEM - Voting Ensemble Model
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
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
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
    from sklearn.svm import SVR, SVC
    from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
    from sklearn.metrics import mean_squared_error, r2_score, accuracy_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class VotingConfig:
    models: List[Any] = field(default_factory=list)
    model_types: List[str] = field(default_factory=list)
    model_configs: List[Dict[str, Any]] = field(default_factory=list)
    voting: str = 'hard'
    weights: Optional[List[float]] = None
    use_proba: bool = False
    n_jobs: int = -1
    random_state: Optional[int] = 42
    verbose: int = 0
    use_gpu: bool = False
    batch_size: int = 256
    learning_rate: float = 0.001
    epochs: int = 100
    early_stopping: bool = False
    patience: int = 5
    validation_ratio: float = 0.0

    def __post_init__(self):
        if self.voting not in ['hard', 'soft', 'weighted']:
            raise ValueError("voting doit être 'hard', 'soft' ou 'weighted'")
        if self.weights is not None and len(self.weights) != len(self.models):
            raise ValueError("Le nombre de poids doit correspondre au nombre de modèles")
        if self.validation_ratio < 0 or self.validation_ratio >= 1:
            raise ValueError("validation_ratio doit être entre 0 et 1")


@dataclass
class VotingResult:
    predictions: np.ndarray
    individual_predictions: List[np.ndarray]
    weights: Optional[List[float]] = None
    confidence: Optional[np.ndarray] = None
    model_scores: Optional[List[float]] = None
    feature_importance: Optional[np.ndarray] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'individual_predictions': [p.tolist() if isinstance(p, np.ndarray) else p for p in self.individual_predictions],
            'weights': self.weights,
            'confidence': self.confidence.tolist() if isinstance(self.confidence, np.ndarray) else self.confidence,
            'model_scores': self.model_scores,
            'feature_importance': self.feature_importance.tolist() if isinstance(self.feature_importance, np.ndarray) else self.feature_importance,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
        }


class VotingEnsemble:
    
    def __init__(self, config: Optional[VotingConfig] = None):
        self.config = config or VotingConfig()
        self.models: List[Any] = []
        self.model_scores: List[float] = []
        self.weights: Optional[List[float]] = None
        self.is_fitted = False
        self.n_features = 0
        self.n_samples = 0
        self.feature_importance: Optional[np.ndarray] = None
        self._prediction_cache: Dict[str, Any] = {}
        
        logger.info(f"VotingEnsemble initialisé avec {len(self.config.models)} modèles")
    
    def _is_regression(self) -> bool:
        return True
    
    def _get_random_state(self, seed: Optional[int] = None) -> np.random.RandomState:
        if seed is None:
            seed = self.config.random_state
        if seed is not None:
            return np.random.RandomState(seed)
        return np.random.RandomState()
    
    def _create_model(self, model_type: str, config: Dict[str, Any], seed: Optional[int] = None) -> Any:
        if seed is not None and 'random_state' not in config:
            config['random_state'] = seed
        
        model_type = model_type.lower()
        
        if model_type == 'linear' and SKLEARN_AVAILABLE:
            return LinearRegression(**config) if self._is_regression() else LogisticRegression(**config)
        
        elif model_type == 'decision_tree' and SKLEARN_AVAILABLE:
            return DecisionTreeRegressor(**config) if self._is_regression() else DecisionTreeClassifier(**config)
        
        elif model_type == 'random_forest' and SKLEARN_AVAILABLE:
            return RandomForestRegressor(**config) if self._is_regression() else RandomForestClassifier(**config)
        
        elif model_type == 'svm' and SKLEARN_AVAILABLE:
            return SVR(**config) if self._is_regression() else SVC(probability=True, **config)
        
        elif model_type == 'knn' and SKLEARN_AVAILABLE:
            return KNeighborsRegressor(**config) if self._is_regression() else KNeighborsClassifier(**config)
        
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
            raise ValueError(f"Modèle non supporté: {model_type}")
    
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
    
    def _evaluate_model(self, model: Any, X: np.ndarray, y: np.ndarray) -> float:
        try:
            predictions = model.predict(X)
            if self._is_regression():
                return r2_score(y, predictions)
            else:
                return accuracy_score(y, predictions)
        except:
            return 0.0
    
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
    
    def _train_model(self, model: Any, X: np.ndarray, y: np.ndarray, X_val: Optional[np.ndarray] = None, y_val: Optional[np.ndarray] = None) -> Dict[str, Any]:
        metrics = {
            'train_time': 0.0,
            'train_score': None,
            'val_score': None,
        }
        
        start_time = datetime.now()
        
        try:
            model_type = str(type(model)).lower()
            
            if 'torch' in model_type and TORCH_AVAILABLE:
                metrics.update(self._train_torch_model(model, X, y, X_val, y_val))
            else:
                if hasattr(model, 'fit'):
                    if hasattr(model, 'set_params') and hasattr(model, 'early_stopping_rounds'):
                        try:
                            if X_val is not None and self.config.early_stopping:
                                eval_set = [(X_val, y_val)]
                                model.fit(X, y, eval_set=eval_set, early_stopping_rounds=self.config.patience, verbose=False)
                            else:
                                model.fit(X, y)
                        except:
                            model.fit(X, y)
                    else:
                        model.fit(X, y)
                    
                    metrics['train_score'] = self._evaluate_model(model, X, y)
                    if X_val is not None:
                        metrics['val_score'] = self._evaluate_model(model, X_val, y_val)
            
            metrics['train_time'] = (datetime.now() - start_time).total_seconds()
            
        except Exception as e:
            logger.error(f"Erreur d'entraînement du modèle: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def _aggregate_predictions(self, individual_preds: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        if not individual_preds:
            raise ValueError("Aucune prédiction à agréger")
        
        if self.config.voting == 'hard':
            if self._is_regression():
                logger.warning("Vote 'hard' utilisé pour la régression, passage à la moyenne")
                predictions = np.mean(individual_preds, axis=0)
            else:
                rounded_preds = np.round(np.array(individual_preds))
                predictions = np.apply_along_axis(
                    lambda x: np.bincount(x.astype(int)).argmax(),
                    axis=0,
                    arr=rounded_preds
                )
        
        elif self.config.voting == 'soft':
            predictions = np.mean(individual_preds, axis=0)
        
        elif self.config.voting == 'weighted':
            if self.weights is None:
                self.weights = np.ones(len(individual_preds)) / len(individual_preds)
            
            weights_norm = np.array(self.weights) / np.sum(self.weights)
            weighted_preds = np.array(individual_preds) * weights_norm[:, np.newaxis]
            predictions = np.sum(weighted_preds, axis=0)
        
        else:
            raise ValueError(f"Méthode de vote non supportée: {self.config.voting}")
        
        confidence = self._compute_confidence(individual_preds)
        
        return predictions, confidence
    
    def _compute_confidence(self, individual_preds: List[np.ndarray]) -> np.ndarray:
        if len(individual_preds) < 2:
            return np.ones_like(individual_preds[0])
        
        if self._is_regression():
            variance = np.var(individual_preds, axis=0)
            if np.std(individual_preds) > 0:
                confidence = 1 - np.sqrt(variance) / (np.std(individual_preds) + 1e-6)
                confidence = np.clip(confidence, 0, 1)
            else:
                confidence = np.ones_like(individual_preds[0])
        else:
            votes = np.array([np.round(pred) for pred in individual_preds])
            agreement = np.apply_along_axis(
                lambda x: np.max(np.bincount(x.astype(int))) / len(individual_preds),
                axis=0,
                arr=votes
            )
            confidence = agreement
        
        return confidence
    
    def _compute_feature_importance(self):
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
            min_len = min(len(imp) for imp in importances)
            trimmed_importances = [imp[:min_len] for imp in importances]
            self.feature_importance = np.mean(trimmed_importances, axis=0)
            if self.feature_importance.sum() > 0:
                self.feature_importance = self.feature_importance / self.feature_importance.sum()
    
    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series]) -> 'VotingEnsemble':
        if isinstance(X, pd.DataFrame):
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values
        
        self.n_samples, self.n_features = X.shape
        self.models = []
        self.model_scores = []
        
        logger.info("Début de l'entraînement du voting ensemble")
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
        
        if self.config.models:
            models_to_train = self.config.models
        else:
            models_to_train = []
            for i, model_type in enumerate(self.config.model_types):
                config = self.config.model_configs[i] if i < len(self.config.model_configs) else {}
                seed = self.config.random_state + i if self.config.random_state is not None else None
                model = self._create_model(model_type, config, seed)
                models_to_train.append(model)
        
        if self.config.n_jobs > 1 and len(models_to_train) > 1:
            with ThreadPoolExecutor(max_workers=self.config.n_jobs) as executor:
                futures = []
                for model in models_to_train:
                    future = executor.submit(self._train_model, model, X_train, y_train, X_val, y_val)
                    futures.append((model, future))
                
                for model, future in futures:
                    try:
                        metrics = future.result(timeout=300)
                        self.models.append(model)
                        score = metrics.get('val_score') or metrics.get('train_score', 0.0)
                        self.model_scores.append(score)
                    except Exception as e:
                        logger.error(f"Erreur d'entraînement parallèle: {e}")
                        continue
        else:
            for model in models_to_train:
                try:
                    metrics = self._train_model(model, X_train, y_train, X_val, y_val)
                    self.models.append(model)
                    score = metrics.get('val_score') or metrics.get('train_score', 0.0)
                    self.model_scores.append(score)
                except Exception as e:
                    logger.error(f"Erreur d'entraînement du modèle: {e}")
                    continue
        
        if not self.models:
            raise RuntimeError("Aucun modèle n'a pu être entraîné")
        
        if self.weights is None and self.config.voting == 'weighted':
            scores = np.array(self.model_scores)
            scores = np.maximum(scores, 0.1)
            self.weights = scores / scores.sum()
        
        self.is_fitted = True
        training_time = (datetime.now() - start_time).total_seconds()
        
        self._compute_feature_importance()
        
        logger.info(f"Entraînement terminé en {training_time:.2f}s")
        logger.info(f"{len(self.models)} modèles entraînés")
        logger.info(f"Méthode de vote: {self.config.voting}")
        
        return self
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame], return_details: bool = False) -> Union[np.ndarray, VotingResult]:
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
                if self.config.use_proba and hasattr(model, 'predict_proba'):
                    pred = model.predict_proba(X)
                    if pred.shape[1] == 2:
                        pred = pred[:, 1]
                else:
                    pred = model.predict(X)
                
                if len(pred.shape) > 1 and pred.shape[1] > 1:
                    pred = pred[:, 0]
                
                individual_preds.append(pred.flatten())
            except Exception as e:
                logger.error(f"Erreur de prédiction pour un modèle: {e}")
                continue
        
        if not individual_preds:
            raise RuntimeError("Aucun modèle n'a pu effectuer de prédiction")
        
        predictions, confidence = self._aggregate_predictions(individual_preds)
        
        result = VotingResult(
            predictions=predictions,
            individual_predictions=individual_preds,
            weights=self.weights,
            confidence=confidence,
            model_scores=self.model_scores,
            feature_importance=self.feature_importance,
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
        
        if self.config.voting == 'hard':
            mean_proba = np.mean(probas, axis=0)
        elif self.config.voting == 'weighted' and self.weights is not None:
            weights_norm = np.array(self.weights) / np.sum(self.weights)
            weighted_probas = np.array(probas) * weights_norm[:, np.newaxis, np.newaxis]
            mean_proba = np.sum(weighted_probas, axis=0)
        else:
            mean_proba = np.mean(probas, axis=0)
        
        return mean_proba
    
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
                'model_scores': self.model_scores,
                'weights': self.weights,
                'feature_importance': self.feature_importance,
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
    def load(cls, filepath: str) -> 'VotingEnsemble':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            ensemble = cls(data['config'])
            ensemble.models = data['models']
            ensemble.model_scores = data.get('model_scores', [])
            ensemble.weights = data.get('weights')
            ensemble.feature_importance = data.get('feature_importance')
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
            'n_models': len(self.models),
            'voting': self.config.voting,
            'weights': self.weights,
            'use_proba': self.config.use_proba,
            'n_jobs': self.config.n_jobs,
            'random_state': self.config.random_state,
            'model_scores': self.model_scores,
            'is_fitted': self.is_fitted,
        }
    
    def get_model_metrics(self) -> Dict[str, Any]:
        return {
            'n_models': len(self.models),
            'voting': self.config.voting,
            'weights': self.weights.tolist() if isinstance(self.weights, np.ndarray) else self.weights,
            'use_proba': self.config.use_proba,
            'model_scores': self.model_scores,
            'n_features': self.n_features,
            'n_samples': self.n_samples,
            'feature_importance': self.feature_importance.tolist() if self.feature_importance is not None else None,
            'is_fitted': self.is_fitted,
            'n_jobs': self.config.n_jobs,
            'random_state': self.config.random_state,
        }


def create_voting_ensemble(
    model_types: List[str],
    voting: str = 'hard',
    weights: Optional[List[float]] = None,
    use_proba: bool = False,
    n_jobs: int = -1,
    random_state: Optional[int] = 42,
    **kwargs
) -> VotingEnsemble:
    config = VotingConfig(
        model_types=model_types,
        voting=voting,
        weights=weights,
        use_proba=use_proba,
        n_jobs=n_jobs,
        random_state=random_state,
        **kwargs
    )
    return VotingEnsemble(config)


__all__ = [
    'VotingEnsemble',
    'VotingConfig',
    'VotingResult',
    'create_voting_ensemble',
]

# ai/models/ensemble/stacking_ensemble.py
"""
NEXUS AI TRADING SYSTEM - Stacking Ensemble Model
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
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
    from sklearn.svm import SVR, SVC
    from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
    from sklearn.model_selection import cross_val_predict, KFold
    from sklearn.metrics import mean_squared_error, r2_score, accuracy_score
    from sklearn.base import BaseEstimator, RegressorMixin, ClassifierMixin, clone
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class StackingConfig:
    base_models: List[Any] = field(default_factory=list)
    base_model_types: List[str] = field(default_factory=list)
    base_model_configs: List[Dict[str, Any]] = field(default_factory=list)
    meta_model_type: str = 'linear'
    meta_model_config: Dict[str, Any] = field(default_factory=dict)
    cv_folds: int = 5
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
        if self.cv_folds < 2:
            raise ValueError("cv_folds doit être >= 2")
        if self.validation_ratio < 0 or self.validation_ratio >= 1:
            raise ValueError("validation_ratio doit être entre 0 et 1")


@dataclass
class StackingResult:
    predictions: np.ndarray
    base_predictions: List[np.ndarray]
    meta_predictions: Optional[np.ndarray] = None
    base_model_scores: Optional[List[float]] = None
    feature_importance: Optional[np.ndarray] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    cv_scores: Optional[List[float]] = None
    meta_model_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'base_predictions': [p.tolist() if isinstance(p, np.ndarray) else p for p in self.base_predictions],
            'meta_predictions': self.meta_predictions.tolist() if isinstance(self.meta_predictions, np.ndarray) else self.meta_predictions,
            'base_model_scores': self.base_model_scores,
            'feature_importance': self.feature_importance.tolist() if isinstance(self.feature_importance, np.ndarray) else self.feature_importance,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'cv_scores': self.cv_scores,
            'meta_model_score': self.meta_model_score,
        }


class StackingEnsemble:
    
    def __init__(self, config: Optional[StackingConfig] = None):
        self.config = config or StackingConfig()
        self.base_models: List[Any] = []
        self.meta_model: Optional[Any] = None
        self.is_fitted = False
        self.n_features = 0
        self.n_samples = 0
        self.base_model_scores: List[float] = []
        self.cv_scores: List[float] = []
        self.feature_importance: Optional[np.ndarray] = None
        self._prediction_cache: Dict[str, Any] = {}
        
        logger.info(f"StackingEnsemble initialisé avec {len(self.config.base_models)} modèles de base")
    
    def _is_regression(self) -> bool:
        return True
    
    def _get_random_state(self, seed: Optional[int] = None) -> np.random.RandomState:
        if seed is None:
            seed = self.config.random_state
        if seed is not None:
            return np.random.RandomState(seed)
        return np.random.RandomState()
    
    def _create_base_model(self, model_type: str, config: Dict[str, Any], seed: Optional[int] = None) -> Any:
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
    
    def _create_meta_model(self, n_features: int) -> Any:
        model_type = self.config.meta_model_type.lower()
        config = self.config.meta_model_config.copy()
        
        if 'random_state' not in config and self.config.random_state is not None:
            config['random_state'] = self.config.random_state
        
        if model_type == 'linear' and SKLEARN_AVAILABLE:
            return LinearRegression(**config) if self._is_regression() else LogisticRegression(**config)
        
        elif model_type == 'decision_tree' and SKLEARN_AVAILABLE:
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
            config['input_dim'] = n_features
            return self._create_torch_model(config)
        
        else:
            raise ValueError(f"Méta-modèle non supporté: {model_type}")
    
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
    
    def _get_base_predictions(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> Tuple[List[np.ndarray], List[float]]:
        predictions = []
        scores = []
        
        for model in self.base_models:
            try:
                if self.config.use_proba and hasattr(model, 'predict_proba'):
                    pred = model.predict_proba(X)
                    if pred.shape[1] == 2:
                        pred = pred[:, 1]
                else:
                    pred = model.predict(X)
                
                if len(pred.shape) > 1 and pred.shape[1] > 1:
                    pred = pred[:, 0]
                
                predictions.append(pred.flatten())
                
                if y is not None:
                    score = self._evaluate_model(model, X, y)
                    scores.append(score)
                else:
                    scores.append(0.0)
                    
            except Exception as e:
                logger.error(f"Erreur de prédiction pour un modèle de base: {e}")
                continue
        
        return predictions, scores
    
    def _get_cv_predictions(self, X: np.ndarray, y: np.ndarray, model: Any) -> np.ndarray:
        try:
            if SKLEARN_AVAILABLE:
                kf = KFold(n_splits=self.config.cv_folds, shuffle=True, random_state=self.config.random_state)
                
                if self.config.use_proba and hasattr(model, 'predict_proba'):
                    predictions = cross_val_predict(
                        model, X, y, cv=kf, method='predict_proba', n_jobs=1
                    )
                    if predictions.shape[1] == 2:
                        predictions = predictions[:, 1]
                else:
                    predictions = cross_val_predict(
                        model, X, y, cv=kf, n_jobs=1
                    )
                
                return predictions.flatten()
            else:
                raise ImportError("Scikit-learn n'est pas installé")
        except Exception as e:
            logger.error(f"Erreur CV pour un modèle: {e}")
            return np.zeros(len(X))
    
    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series]) -> 'StackingEnsemble':
        if isinstance(X, pd.DataFrame):
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values
        
        self.n_samples, self.n_features = X.shape
        self.base_models = []
        self.base_model_scores = []
        
        logger.info("Début de l'entraînement du stacking ensemble")
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
        
        if self.config.base_models:
            base_models = self.config.base_models
        else:
            base_models = []
            for i, model_type in enumerate(self.config.base_model_types):
                config = self.config.base_model_configs[i] if i < len(self.config.base_model_configs) else {}
                seed = self.config.random_state + i if self.config.random_state is not None else None
                model = self._create_base_model(model_type, config, seed)
                base_models.append(model)
        
        if self.config.n_jobs > 1 and len(base_models) > 1:
            with ThreadPoolExecutor(max_workers=self.config.n_jobs) as executor:
                futures = []
                for model in base_models:
                    future = executor.submit(self._train_model, model, X_train, y_train, X_val, y_val)
                    futures.append((model, future))
                
                trained_models = []
                for model, future in futures:
                    try:
                        trained_models.append((model, future.result(timeout=300)))
                    except Exception as e:
                        logger.error(f"Erreur d'entraînement parallèle: {e}")
                        continue
        else:
            trained_models = []
            for model in base_models:
                try:
                    metrics = self._train_model(model, X_train, y_train, X_val, y_val)
                    trained_models.append((model, metrics))
                except Exception as e:
                    logger.error(f"Erreur d'entraînement du modèle: {e}")
                    continue
        
        self.base_models = []
        self.base_model_scores = []
        
        for model, metrics in trained_models:
            self.base_models.append(model)
            score = metrics.get('val_score') or metrics.get('train_score', 0.0)
            self.base_model_scores.append(score)
        
        if not self.base_models:
            raise RuntimeError("Aucun modèle de base n'a pu être entraîné")
        
        logger.info(f"{len(self.base_models)} modèles de base entraînés")
        
        cv_predictions = []
        for model in self.base_models:
            try:
                pred = self._get_cv_predictions(X_train, y_train, model)
                cv_predictions.append(pred.reshape(-1, 1))
            except Exception as e:
                logger.error(f"Erreur CV pour un modèle: {e}")
                pred = np.zeros((len(X_train), 1))
                cv_predictions.append(pred)
        
        X_meta = np.hstack(cv_predictions) if len(cv_predictions) > 1 else cv_predictions[0].reshape(-1, 1)
        
        if self.config.use_proba and hasattr(self.base_models[0], 'predict_proba'):
            X_meta = np.hstack([pred.reshape(-1, 1) for pred in cv_predictions])
        else:
            X_meta = np.hstack(cv_predictions)
        
        self.meta_model = self._create_meta_model(X_meta.shape[1])
        
        meta_metrics = self._train_model(self.meta_model, X_meta, y_train, None, None)
        logger.info("Méta-modèle entraîné")
        
        self.is_fitted = True
        training_time = (datetime.now() - start_time).total_seconds()
        
        self._compute_feature_importance()
        
        logger.info(f"Entraînement terminé en {training_time:.2f}s")
        logger.info(f"Score du méta-modèle: {meta_metrics.get('train_score', 0.0):.4f}")
        
        return self
    
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
    
    def _compute_feature_importance(self):
        importances = []
        
        if hasattr(self.meta_model, 'feature_importances_'):
            importances.append(self.meta_model.feature_importances_)
        elif hasattr(self.meta_model, 'coef_'):
            importances.append(np.abs(self.meta_model.coef_).flatten())
        
        for model in self.base_models:
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
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame], return_details: bool = False) -> Union[np.ndarray, StackingResult]:
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        cache_key = str(hash(X.tobytes()))
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            return self._prediction_cache[cache_key]
        
        base_preds, scores = self._get_base_predictions(X)
        
        if not base_preds:
            raise RuntimeError("Aucun modèle de base n'a pu effectuer de prédiction")
        
        X_meta = np.hstack([pred.reshape(-1, 1) for pred in base_preds]) if len(base_preds) > 1 else base_preds[0].reshape(-1, 1)
        
        try:
            if self.config.use_proba and hasattr(self.meta_model, 'predict_proba'):
                meta_pred = self.meta_model.predict_proba(X_meta)
                if meta_pred.shape[1] == 2:
                    meta_pred = meta_pred[:, 1]
            else:
                meta_pred = self.meta_model.predict(X_meta)
            
            if len(meta_pred.shape) > 1 and meta_pred.shape[1] > 1:
                meta_pred = meta_pred[:, 0]
            
            meta_pred = meta_pred.flatten()
        except Exception as e:
            logger.error(f"Erreur de prédiction du méta-modèle: {e}")
            meta_pred = np.mean(base_preds, axis=0)
        
        result = StackingResult(
            predictions=meta_pred,
            base_predictions=base_preds,
            meta_predictions=meta_pred,
            base_model_scores=scores,
            feature_importance=self.feature_importance,
            cv_scores=self.cv_scores if hasattr(self, 'cv_scores') else None,
            meta_model_score=0.0,
        )
        
        self._prediction_cache[cache_key] = result if return_details else meta_pred
        
        return result if return_details else meta_pred
    
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")
        
        if self._is_regression():
            raise ValueError("predict_proba n'est pas supporté pour la régression")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        base_probas = []
        for model in self.base_models:
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X)
                base_probas.append(proba)
        
        if not base_probas:
            raise RuntimeError("Aucun modèle ne supporte predict_proba")
        
        X_meta = np.hstack([proba.reshape(-1, 1) if len(proba.shape) == 1 else proba for proba in base_probas])
        
        if hasattr(self.meta_model, 'predict_proba'):
            return self.meta_model.predict_proba(X_meta)
        else:
            return np.mean(base_probas, axis=0)
    
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
                'base_models': self.base_models,
                'meta_model': self.meta_model,
                'base_model_scores': self.base_model_scores,
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
    def load(cls, filepath: str) -> 'StackingEnsemble':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            ensemble = cls(data['config'])
            ensemble.base_models = data['base_models']
            ensemble.meta_model = data['meta_model']
            ensemble.base_model_scores = data.get('base_model_scores', [])
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
            'n_base_models': len(self.base_models),
            'meta_model_type': self.config.meta_model_type,
            'cv_folds': self.config.cv_folds,
            'use_proba': self.config.use_proba,
            'n_jobs': self.config.n_jobs,
            'random_state': self.config.random_state,
            'base_model_types': self.config.base_model_types,
            'base_model_scores': self.base_model_scores,
            'is_fitted': self.is_fitted,
        }
    
    def get_model_metrics(self) -> Dict[str, Any]:
        return {
            'n_base_models': len(self.base_models),
            'base_model_scores': self.base_model_scores,
            'meta_model_type': self.config.meta_model_type,
            'cv_folds': self.config.cv_folds,
            'use_proba': self.config.use_proba,
            'n_features': self.n_features,
            'n_samples': self.n_samples,
            'feature_importance': self.feature_importance.tolist() if self.feature_importance is not None else None,
            'is_fitted': self.is_fitted,
            'n_jobs': self.config.n_jobs,
            'random_state': self.config.random_state,
        }


def create_stacking_ensemble(
    base_model_types: List[str],
    meta_model_type: str = 'linear',
    cv_folds: int = 5,
    use_proba: bool = False,
    n_jobs: int = -1,
    random_state: Optional[int] = 42,
    **kwargs
) -> StackingEnsemble:
    config = StackingConfig(
        base_model_types=base_model_types,
        meta_model_type=meta_model_type,
        cv_folds=cv_folds,
        use_proba=use_proba,
        n_jobs=n_jobs,
        random_state=random_state,
        **kwargs
    )
    return StackingEnsemble(config)


__all__ = [
    'StackingEnsemble',
    'StackingConfig',
    'StackingResult',
    'create_stacking_ensemble',
]

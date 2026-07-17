"""
NEXUS AI TRADING SYSTEM - LSTM Model for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/models/lstm_model.py
Description: Modèle LSTM (Long Short-Term Memory) pour le bot AI.
             Supporte les architectures LSTM, BiLSTM, Stacked LSTM,
             Attention LSTM, et LSTM avec couches convolutives.
             Intègre PyTorch avec support GPU et optimisation.
"""

import asyncio
import logging
import time
import json
import os
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    optim = None
    DataLoader = None
    TensorDataset = None

from trading.bots.ai_bot.models.base_model import (
    BaseModel,
    ModelConfig,
    ModelMetrics,
    PredictionResult,
    ModelType,
    ModelTask
)
from shared.exceptions import ModelError

# Configuration du logging
logger = logging.getLogger(__name__)


class LSTMLayerType(Enum):
    """Types de couches LSTM."""
    LSTM = "lstm"
    BILSTM = "bilstm"
    STACKED_LSTM = "stacked_lstm"
    ATTENTION_LSTM = "attention_lstm"
    CONV_LSTM = "conv_lstm"


@dataclass
class LSTMConfig(ModelConfig):
    """
    Configuration du modèle LSTM.
    """
    # Architecture LSTM
    lstm_type: LSTMLayerType = LSTMLayerType.LSTM
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.2
    bidirectional: bool = False
    
    # Couches supplémentaires
    use_attention: bool = False
    attention_heads: int = 4
    use_conv: bool = False
    conv_filters: int = 32
    conv_kernel_size: int = 3
    
    # Paramètres d'entraînement
    optimizer: str = "adam"  # 'adam', 'sgd', 'rmsprop'
    weight_decay: float = 1e-5
    gradient_clip: float = 1.0
    scheduler: str = "none"  # 'none', 'step', 'cosine', 'reduce_on_plateau'
    scheduler_params: Dict[str, Any] = field(default_factory=dict)
    
    # Paramètres de données
    sequence_length: int = 50
    lookahead: int = 1
    feature_scaling: bool = True
    
    # Paramètres avancés
    use_batch_norm: bool = True
    use_layer_norm: bool = False
    activation: str = "tanh"  # 'tanh', 'relu', 'leaky_relu'
    
    def __post_init__(self):
        """Validation des paramètres."""
        super().__post_init__()
        
        if not TORCH_AVAILABLE:
            raise ModelError("PyTorch non installé")
        
        if self.hidden_size < 1:
            raise ModelError("hidden_size doit être >= 1")
        
        if self.num_layers < 1:
            raise ModelError("num_layers doit être >= 1")
        
        if self.dropout < 0 or self.dropout > 1:
            raise ModelError("dropout doit être entre 0 et 1")
        
        if self.sequence_length < 2:
            raise ModelError("sequence_length doit être >= 2")
        
        if self.lookahead < 1:
            raise ModelError("lookahead doit être >= 1")
        
        self.model_type = ModelType.PYTORCH


class LSTMModel(BaseModel):
    """
    Modèle LSTM pour le trading.
    """
    
    def __init__(self, config: LSTMConfig):
        """
        Initialise le modèle LSTM.
        
        Args:
            config: Configuration du modèle LSTM.
        """
        super().__init__(config)
        self.lstm_config = config
        
        # Vérification PyTorch
        if not TORCH_AVAILABLE:
            raise ModelError("PyTorch est requis pour le modèle LSTM")
        
        # Modèle PyTorch
        self._model = None
        self._optimizer = None
        self._scheduler = None
        self._criterion = None
        
        # Device
        self._device = torch.device(self.config.device)
        
        # État
        self._best_loss = float('inf')
        self._patience_counter = 0
        
        logger.info(f"LSTMModel initialisé: {config.lstm_type.value}")
        logger.info(f"Hidden size: {config.hidden_size}, Layers: {config.num_layers}")
        logger.info(f"Device: {self._device}")
    
    # ============================================================
    # CONSTRUCTION DU MODÈLE
    # ============================================================
    
    def build(self, input_shape: Tuple[int, ...]) -> None:
        """
        Construit l'architecture LSTM.
        
        Args:
            input_shape: Forme des données d'entrée.
        """
        logger.info(f"Construction du modèle LSTM avec input_shape={input_shape}")
        
        self.config.input_shape = input_shape
        
        # Création du modèle
        self._model = self._create_model(input_shape)
        self._model.to(self._device)
        
        # Création de l'optimizer
        self._optimizer = self._create_optimizer()
        
        # Création du scheduler
        self._scheduler = self._create_scheduler()
        
        # Création de la fonction de loss
        self._criterion = self._create_criterion()
        
        self._is_built = True
        
        logger.info(f"Modèle LSTM construit avec {self._count_parameters()} paramètres")
    
    def _create_model(self, input_shape: Tuple[int, ...]) -> nn.Module:
        """
        Crée le modèle PyTorch.
        
        Args:
            input_shape: Forme des données d'entrée.
            
        Returns:
            Modèle PyTorch.
        """
        if self.lstm_config.lstm_type == LSTMLayerType.LSTM:
            return self._create_basic_lstm(input_shape)
        elif self.lstm_config.lstm_type == LSTMLayerType.BILSTM:
            return self._create_bilstm(input_shape)
        elif self.lstm_config.lstm_type == LSTMLayerType.STACKED_LSTM:
            return self._create_stacked_lstm(input_shape)
        elif self.lstm_config.lstm_type == LSTMLayerType.ATTENTION_LSTM:
            return self._create_attention_lstm(input_shape)
        elif self.lstm_config.lstm_type == LSTMLayerType.CONV_LSTM:
            return self._create_conv_lstm(input_shape)
        else:
            return self._create_basic_lstm(input_shape)
    
    def _create_basic_lstm(self, input_shape: Tuple[int, ...]) -> nn.Module:
        """
        Crée un LSTM de base.
        
        Args:
            input_shape: Forme des données d'entrée.
            
        Returns:
            Module PyTorch.
        """
        class LSTMModel(nn.Module):
            def __init__(self, config):
                super().__init__()
                
                input_size = input_shape[-1]
                hidden_size = config.hidden_size
                num_layers = config.num_layers
                dropout = config.dropout
                output_size = 1
                
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0,
                    bidirectional=False
                )
                
                self.dropout = nn.Dropout(dropout)
                self.fc = nn.Linear(hidden_size, output_size)
                
                if config.use_batch_norm:
                    self.bn = nn.BatchNorm1d(hidden_size)
                else:
                    self.bn = None
            
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                last_out = lstm_out[:, -1, :]
                
                if self.bn is not None:
                    last_out = self.bn(last_out)
                
                last_out = self.dropout(last_out)
                return self.fc(last_out)
        
        return LSTMModel(self.lstm_config)
    
    def _create_bilstm(self, input_shape: Tuple[int, ...]) -> nn.Module:
        """
        Crée un BiLSTM.
        
        Args:
            input_shape: Forme des données d'entrée.
            
        Returns:
            Module PyTorch.
        """
        class BiLSTMModel(nn.Module):
            def __init__(self, config):
                super().__init__()
                
                input_size = input_shape[-1]
                hidden_size = config.hidden_size
                num_layers = config.num_layers
                dropout = config.dropout
                output_size = 1
                
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0,
                    bidirectional=True
                )
                
                self.dropout = nn.Dropout(dropout)
                self.fc = nn.Linear(hidden_size * 2, output_size)
                
                if config.use_batch_norm:
                    self.bn = nn.BatchNorm1d(hidden_size * 2)
                else:
                    self.bn = None
            
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                last_out = lstm_out[:, -1, :]
                
                if self.bn is not None:
                    last_out = self.bn(last_out)
                
                last_out = self.dropout(last_out)
                return self.fc(last_out)
        
        return BiLSTMModel(self.lstm_config)
    
    def _create_stacked_lstm(self, input_shape: Tuple[int, ...]) -> nn.Module:
        """
        Crée un Stacked LSTM.
        
        Args:
            input_shape: Forme des données d'entrée.
            
        Returns:
            Module PyTorch.
        """
        class StackedLSTMModel(nn.Module):
            def __init__(self, config):
                super().__init__()
                
                input_size = input_shape[-1]
                hidden_size = config.hidden_size
                num_layers = config.num_layers
                dropout = config.dropout
                output_size = 1
                
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0,
                    bidirectional=False
                )
                
                self.dropout = nn.Dropout(dropout)
                
                self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
                self.fc2 = nn.Linear(hidden_size // 2, output_size)
                
                self.relu = nn.ReLU()
                
                if config.use_batch_norm:
                    self.bn = nn.BatchNorm1d(hidden_size // 2)
                else:
                    self.bn = None
            
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                last_out = lstm_out[:, -1, :]
                last_out = self.dropout(last_out)
                
                out = self.fc1(last_out)
                out = self.relu(out)
                
                if self.bn is not None:
                    out = self.bn(out)
                
                out = self.dropout(out)
                return self.fc2(out)
        
        return StackedLSTMModel(self.lstm_config)
    
    def _create_attention_lstm(self, input_shape: Tuple[int, ...]) -> nn.Module:
        """
        Crée un LSTM avec attention.
        
        Args:
            input_shape: Forme des données d'entrée.
            
        Returns:
            Module PyTorch.
        """
        class AttentionLSTMModel(nn.Module):
            def __init__(self, config):
                super().__init__()
                
                input_size = input_shape[-1]
                hidden_size = config.hidden_size
                num_layers = config.num_layers
                dropout = config.dropout
                output_size = 1
                num_heads = config.attention_heads
                
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0,
                    bidirectional=False
                )
                
                self.attention = nn.MultiheadAttention(
                    embed_dim=hidden_size,
                    num_heads=min(num_heads, hidden_size),
                    batch_first=True,
                    dropout=dropout
                )
                
                self.dropout = nn.Dropout(dropout)
                self.fc = nn.Linear(hidden_size, output_size)
                
                if config.use_batch_norm:
                    self.bn = nn.BatchNorm1d(hidden_size)
                else:
                    self.bn = None
            
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
                last_out = attn_out[:, -1, :]
                
                if self.bn is not None:
                    last_out = self.bn(last_out)
                
                last_out = self.dropout(last_out)
                return self.fc(last_out)
        
        return AttentionLSTMModel(self.lstm_config)
    
    def _create_conv_lstm(self, input_shape: Tuple[int, ...]) -> nn.Module:
        """
        Crée un ConvLSTM.
        
        Args:
            input_shape: Forme des données d'entrée.
            
        Returns:
            Module PyTorch.
        """
        class ConvLSTMModel(nn.Module):
            def __init__(self, config):
                super().__init__()
                
                input_size = input_shape[-1]
                hidden_size = config.hidden_size
                num_layers = config.num_layers
                dropout = config.dropout
                output_size = 1
                conv_filters = config.conv_filters
                conv_kernel = config.conv_kernel_size
                
                self.conv = nn.Conv1d(
                    in_channels=input_size,
                    out_channels=conv_filters,
                    kernel_size=conv_kernel,
                    padding=conv_kernel // 2
                )
                
                self.lstm = nn.LSTM(
                    input_size=conv_filters,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0,
                    bidirectional=False
                )
                
                self.dropout = nn.Dropout(dropout)
                self.fc = nn.Linear(hidden_size, output_size)
                
                self.relu = nn.ReLU()
                
                if config.use_batch_norm:
                    self.bn = nn.BatchNorm1d(hidden_size)
                else:
                    self.bn = None
            
            def forward(self, x):
                # x: [batch, seq_len, features]
                x = x.permute(0, 2, 1)  # [batch, features, seq_len]
                x = self.conv(x)  # [batch, conv_filters, seq_len]
                x = self.relu(x)
                x = x.permute(0, 2, 1)  # [batch, seq_len, conv_filters]
                
                lstm_out, _ = self.lstm(x)
                last_out = lstm_out[:, -1, :]
                
                if self.bn is not None:
                    last_out = self.bn(last_out)
                
                last_out = self.dropout(last_out)
                return self.fc(last_out)
        
        return ConvLSTMModel(self.lstm_config)
    
    def _create_optimizer(self) -> torch.optim.Optimizer:
        """
        Crée l'optimizer.
        
        Returns:
            Optimizer PyTorch.
        """
        if self.lstm_config.optimizer == "adam":
            return optim.Adam(
                self._model.parameters(),
                lr=self.lstm_config.learning_rate,
                weight_decay=self.lstm_config.weight_decay
            )
        elif self.lstm_config.optimizer == "sgd":
            return optim.SGD(
                self._model.parameters(),
                lr=self.lstm_config.learning_rate,
                momentum=0.9,
                weight_decay=self.lstm_config.weight_decay
            )
        elif self.lstm_config.optimizer == "rmsprop":
            return optim.RMSprop(
                self._model.parameters(),
                lr=self.lstm_config.learning_rate,
                weight_decay=self.lstm_config.weight_decay
            )
        else:
            return optim.Adam(
                self._model.parameters(),
                lr=self.lstm_config.learning_rate,
                weight_decay=self.lstm_config.weight_decay
            )
    
    def _create_scheduler(self) -> Optional[torch.optim.lr_scheduler._LRScheduler]:
        """
        Crée le scheduler.
        
        Returns:
            Scheduler PyTorch ou None.
        """
        if self.lstm_config.scheduler == "step":
            return optim.lr_scheduler.StepLR(
                self._optimizer,
                step_size=self.lstm_config.scheduler_params.get('step_size', 10),
                gamma=self.lstm_config.scheduler_params.get('gamma', 0.1)
            )
        elif self.lstm_config.scheduler == "cosine":
            return optim.lr_scheduler.CosineAnnealingLR(
                self._optimizer,
                T_max=self.lstm_config.scheduler_params.get('T_max', 50)
            )
        elif self.lstm_config.scheduler == "reduce_on_plateau":
            return optim.lr_scheduler.ReduceLROnPlateau(
                self._optimizer,
                patience=self.lstm_config.scheduler_params.get('patience', 10),
                factor=self.lstm_config.scheduler_params.get('factor', 0.5)
            )
        else:
            return None
    
    def _create_criterion(self) -> nn.Module:
        """
        Crée la fonction de loss.
        
        Returns:
            Fonction de loss PyTorch.
        """
        if self.config.task == ModelTask.CLASSIFICATION:
            if self.config.params.get('num_classes', 2) > 2:
                return nn.CrossEntropyLoss()
            else:
                return nn.BCEWithLogitsLoss()
        else:
            return nn.MSELoss()
    
    def _count_parameters(self) -> int:
        """
        Compte les paramètres du modèle.
        
        Returns:
            Nombre de paramètres.
        """
        return sum(p.numel() for p in self._model.parameters() if p.requires_grad)
    
    # ============================================================
    # ENTRAÎNEMENT
    # ============================================================
    
    def train(
        self,
        X_train: Union[np.ndarray, pd.DataFrame],
        y_train: Union[np.ndarray, pd.DataFrame],
        X_val: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y_val: Optional[Union[np.ndarray, pd.DataFrame]] = None
    ) -> ModelMetrics:
        """
        Entraîne le modèle LSTM.
        
        Args:
            X_train: Données d'entraînement.
            y_train: Labels d'entraînement.
            X_val: Données de validation.
            y_val: Labels de validation.
            
        Returns:
            Métriques d'entraînement.
        """
        if not self._is_built:
            raise ModelError("Modèle non construit")
        
        logger.info(f"Entraînement du modèle LSTM sur {len(X_train)} échantillons")
        
        start_time = time.time()
        
        # Conversion des données
        X_train = self._prepare_data(X_train)
        y_train = self._to_tensor(y_train)
        
        # Création des DataLoader
        train_dataset = TensorDataset(X_train, y_train)
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.lstm_config.batch_size,
            shuffle=True
        )
        
        if X_val is not None and y_val is not None:
            X_val = self._prepare_data(X_val)
            y_val = self._to_tensor(y_val)
            val_dataset = TensorDataset(X_val, y_val)
            val_loader = DataLoader(
                val_dataset,
                batch_size=self.lstm_config.batch_size,
                shuffle=False
            )
        else:
            val_loader = None
        
        # Entraînement
        self._model.train()
        train_losses = []
        val_losses = []
        train_accuracies = []
        val_accuracies = []
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.lstm_config.epochs):
            # Entraînement
            train_loss = self._train_epoch(train_loader)
            train_losses.append(train_loss)
            
            # Validation
            if val_loader:
                val_loss, val_acc = self._validate_epoch(val_loader)
                val_losses.append(val_loss)
                val_accuracies.append(val_acc)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    # Sauvegarde du meilleur modèle
                    if self.lstm_config.save_best:
                        self.save_checkpoint(epoch, self.metrics, is_best=True)
                else:
                    patience_counter += 1
                    
                    if self.lstm_config.early_stopping and patience_counter >= self.lstm_config.patience:
                        logger.info(f"Early stopping à l'époque {epoch}")
                        break
            else:
                # Pas de validation
                if train_loss < self._best_loss:
                    self._best_loss = train_loss
                    if self.lstm_config.save_best:
                        self.save_checkpoint(epoch, self.metrics, is_best=True)
            
            # Scheduler
            if self._scheduler:
                if isinstance(self._scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    self._scheduler.step(val_losses[-1] if val_losses else train_losses[-1])
                else:
                    self._scheduler.step()
            
            # Logging
            if (epoch + 1) % 10 == 0:
                log_msg = f"Epoch {epoch+1}/{self.lstm_config.epochs} - Train Loss: {train_loss:.4f}"
                if val_loader:
                    log_msg += f" - Val Loss: {val_loss:.4f}"
                    if self.config.task == ModelTask.CLASSIFICATION:
                        log_msg += f" - Val Acc: {val_acc:.4f}"
                logger.info(log_msg)
        
        # Métriques finales
        self.metrics.train_loss = train_losses
        self.metrics.val_loss = val_losses
        self.metrics.train_accuracy = train_accuracies
        self.metrics.val_accuracy = val_accuracies
        self.metrics.total_epochs = len(train_losses)
        self.metrics.training_time_s = time.time() - start_time
        
        # Évaluation finale sur la validation
        if val_loader:
            final_val_loss, final_val_acc = self._validate_epoch(val_loader)
            self.metrics.loss = final_val_loss
            self.metrics.accuracy = final_val_acc
        
        self._is_trained = True
        
        logger.info(f"Entraînement terminé: {self.metrics.total_epochs} époques")
        
        return self.metrics
    
    def _train_epoch(self, loader: DataLoader) -> float:
        """
        Entraîne une époque.
        
        Args:
            loader: DataLoader d'entraînement.
            
        Returns:
            Loss moyenne de l'époque.
        """
        self._model.train()
        total_loss = 0.0
        
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(self._device)
            batch_y = batch_y.to(self._device)
            
            self._optimizer.zero_grad()
            
            predictions = self._model(batch_x)
            loss = self._criterion(predictions, batch_y)
            
            loss.backward()
            
            # Gradient clipping
            if self.lstm_config.gradient_clip > 0:
                torch.nn.utils.clip_grad_norm_(
                    self._model.parameters(),
                    self.lstm_config.gradient_clip
                )
            
            self._optimizer.step()
            
            total_loss += loss.item()
        
        return total_loss / len(loader)
    
    def _validate_epoch(self, loader: DataLoader) -> Tuple[float, float]:
        """
        Valide une époque.
        
        Args:
            loader: DataLoader de validation.
            
        Returns:
            Tuple (loss, accuracy).
        """
        self._model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self._device)
                batch_y = batch_y.to(self._device)
                
                predictions = self._model(batch_x)
                loss = self._criterion(predictions, batch_y)
                
                total_loss += loss.item()
                
                if self.config.task == ModelTask.CLASSIFICATION:
                    if predictions.shape[1] > 1:
                        _, predicted = torch.max(predictions, 1)
                        _, target = torch.max(batch_y, 1)
                    else:
                        predicted = (predictions > 0.5).float()
                        target = batch_y
                    
                    correct += (predicted == target).sum().item()
                    total += batch_y.size(0)
        
        avg_loss = total_loss / len(loader)
        accuracy = correct / total if total > 0 else 0.0
        
        return avg_loss, accuracy
    
    # ============================================================
    # PRÉDICTION
    # ============================================================
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> PredictionResult:
        """
        Effectue une prédiction.
        
        Args:
            X: Données à prédire.
            
        Returns:
            Résultat de la prédiction.
        """
        if not self._is_trained and not self._is_loaded:
            raise ModelError("Modèle non entraîné ou chargé")
        
        start_time = time.time()
        
        # Préparation des données
        X = self._prepare_data(X)
        X = X.to(self._device)
        
        # Prédiction
        self._model.eval()
        with torch.no_grad():
            predictions = self._model(X)
            predictions = predictions.cpu().numpy()
        
        # Post-traitement
        if self.config.task == ModelTask.CLASSIFICATION:
            if predictions.shape[1] > 1:
                predictions = np.argmax(predictions, axis=1)
            else:
                predictions = (predictions > 0.5).astype(np.float32)
        
        result = PredictionResult(
            predictions=predictions,
            timestamp=datetime.now(),
            input_shape=X.shape,
            inference_time_ms=(time.time() - start_time) * 1000
        )
        
        return result
    
    # ============================================================
    # SAUVEGARDE ET CHARGEMENT
    # ============================================================
    
    def save(self, filepath: str) -> None:
        """
        Sauvegarde le modèle LSTM.
        
        Args:
            filepath: Chemin de sauvegarde.
        """
        logger.info(f"Sauvegarde du modèle LSTM: {filepath}")
        
        if self._model is None:
            raise ModelError("Modèle non construit")
        
        # Sauvegarde du modèle
        torch.save({
            'model_state_dict': self._model.state_dict(),
            'config': self.lstm_config.__dict__,
            'metrics': self.metrics.to_dict(),
            'is_trained': self._is_trained,
            'input_shape': self.config.input_shape
        }, filepath)
        
        # Sauvegarde de la configuration
        config_path = filepath.replace('.pth', '_config.json')
        with open(config_path, 'w') as f:
            json.dump(self.lstm_config.__dict__, f, indent=2, default=str)
        
        logger.info(f"Modèle LSTM sauvegardé: {filepath}")
    
    def load(self, filepath: str) -> None:
        """
        Charge le modèle LSTM.
        
        Args:
            filepath: Chemin de chargement.
        """
        logger.info(f"Chargement du modèle LSTM: {filepath}")
        
        if not os.path.exists(filepath):
            raise ModelError(f"Fichier non trouvé: {filepath}")
        
        try:
            # Chargement du checkpoint
            checkpoint = torch.load(filepath, map_location=self._device)
            
            # Récupération de la configuration
            if 'config' in checkpoint:
                config_dict = checkpoint['config']
                self.lstm_config = LSTMConfig(**config_dict)
            
            # Récupération de l'input_shape
            if 'input_shape' in checkpoint:
                self.config.input_shape = checkpoint['input_shape']
            
            # Construction du modèle
            self.build(self.config.input_shape)
            
            # Chargement des poids
            self._model.load_state_dict(checkpoint['model_state_dict'])
            self._model.to(self._device)
            
            # Récupération des métriques
            if 'metrics' in checkpoint:
                self.metrics = ModelMetrics(**checkpoint['metrics'])
            
            # Récupération de l'état entraîné
            if 'is_trained' in checkpoint:
                self._is_trained = checkpoint['is_trained']
            
            self._is_loaded = True
            
            logger.info(f"Modèle LSTM chargé: {filepath}")
            
        except Exception as e:
            logger.error(f"Erreur de chargement du modèle: {e}")
            raise ModelError(f"Erreur de chargement: {e}")
    
    def get_params(self) -> Dict[str, Any]:
        """
        Retourne les paramètres du modèle.
        
        Returns:
            Paramètres du modèle.
        """
        params = {
            'lstm_type': self.lstm_config.lstm_type.value,
            'hidden_size': self.lstm_config.hidden_size,
            'num_layers': self.lstm_config.num_layers,
            'dropout': self.lstm_config.dropout,
            'bidirectional': self.lstm_config.bidirectional,
            'use_attention': self.lstm_config.use_attention,
            'sequence_length': self.lstm_config.sequence_length,
            'lookahead': self.lstm_config.lookahead,
            'total_parameters': self._count_parameters()
        }
        return params
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _prepare_data(self, data: Union[np.ndarray, pd.DataFrame]) -> torch.Tensor:
        """
        Prépare les données pour le modèle.
        
        Args:
            data: Données à préparer.
            
        Returns:
            Tensor PyTorch.
        """
        if isinstance(data, pd.DataFrame):
            data = data.values
        
        # Redimensionnement pour LSTM
        if len(data.shape) == 2:
            # Ajout de la dimension de séquence
            data = data.reshape(data.shape[0], self.lstm_config.sequence_length, -1)
        
        return torch.FloatTensor(data).to(self._device)
    
    def _to_tensor(self, data: Union[np.ndarray, pd.DataFrame]) -> torch.Tensor:
        """
        Convertit en Tensor PyTorch.
        
        Args:
            data: Données à convertir.
            
        Returns:
            Tensor PyTorch.
        """
        if isinstance(data, pd.DataFrame):
            data = data.values
        
        if self.config.task == ModelTask.CLASSIFICATION:
            if data.ndim == 1:
                data = data.reshape(-1, 1)
        
        return torch.FloatTensor(data).to(self._device)


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_lstm_model(
    input_shape: Tuple[int, ...],
    lstm_type: str = "lstm",
    hidden_size: int = 64,
    num_layers: int = 2,
    sequence_length: int = 50,
    **kwargs
) -> LSTMModel:
    """
    Crée un modèle LSTM.
    
    Args:
        input_shape: Forme des données d'entrée.
        lstm_type: Type de LSTM.
        hidden_size: Taille cachée.
        num_layers: Nombre de couches.
        sequence_length: Longueur de séquence.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Modèle LSTM.
    """
    lstm_type_map = {
        'lstm': LSTMLayerType.LSTM,
        'bilstm': LSTMLayerType.BILSTM,
        'stacked': LSTMLayerType.STACKED_LSTM,
        'attention': LSTMLayerType.ATTENTION_LSTM,
        'conv_lstm': LSTMLayerType.CONV_LSTM
    }
    
    config = LSTMConfig(
        lstm_type=lstm_type_map.get(lstm_type, LSTMLayerType.LSTM),
        hidden_size=hidden_size,
        num_layers=num_layers,
        sequence_length=sequence_length,
        **kwargs
    )
    
    model = LSTMModel(config)
    model.build(input_shape)
    return model


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'LSTMModel',
    'LSTMConfig',
    'LSTMLayerType',
    'create_lstm_model'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
